# Builds and updates the inverted index; synchronises index state with Redis.
import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.core.nlp_pipeline import NLPPipeline
from app.data.models import Document, IndexEntry
from app.data.redis_client import get_redis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDIS_INDEX_TTL = 86400          # 24 hours in seconds
TFIDF_MAX_FEATURES = 50_000

# ---------------------------------------------------------------------------
# Module-level shared state
# ---------------------------------------------------------------------------

# The fitted vectorizer and document matrix are kept in memory after build.
# They are rebuilt on server restart (as per PRD Section 12).
_vectorizer: TfidfVectorizer | None = None
_doc_matrix = None          # sparse matrix  (n_docs × n_features)
_doc_ids: list[str] = []    # parallel list — index matches _doc_matrix rows


class IndexService:
    """
    Manages the inverted index lifecycle:
      - build_full_index   : fit TF-IDF on all documents, persist to PostgreSQL, cache in Redis
      - update_index       : incremental update for a single new document
      - get_index_from_cache : Redis-first lookup with PostgreSQL fallback
      - sync_to_postgres   : write in-memory index to index_entries table
    """

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
        self.nlp = NLPPipeline()

    # ------------------------------------------------------------------
    # 1. Build full index

    def build_full_index(self, docs: list[Document]) -> None:
        """
        Fit TF-IDF vectorizer on all documents, store scores in PostgreSQL,
        and prime the Redis cache for every term.

        Called once at server startup via the ingestion script.
        """
        global _vectorizer, _doc_matrix, _doc_ids

        if not docs:
            return

        # Preprocess each document body into a joined token string
        # (TfidfVectorizer expects raw strings; we supply pre-tokenised text
        #  joined back so our NLP pipeline drives tokenisation)
        corpus = [" ".join(self.nlp.process(doc.body)) for doc in docs]
        _doc_ids = [str(doc.id) for doc in docs]

        # Fit vectorizer
        _vectorizer = TfidfVectorizer(
            sublinear_tf=True,
            min_df=1,
            max_features=TFIDF_MAX_FEATURES,
            analyzer="word",
            norm="l2",
        )
        _doc_matrix = _vectorizer.fit_transform(corpus)

        # Persist to PostgreSQL
        self.sync_to_postgres(docs)

        # Prime Redis cache
        self._prime_redis_cache()

    # ------------------------------------------------------------------
    # 2. Full rebuild for every new upload

    def update_index(self, doc: Document) -> None:
        """
        Add a single newly uploaded document to the in-memory index.
        Rebuilds the full index to include new vocabulary terms.
        """
        global _vectorizer, _doc_matrix, _doc_ids

        # Always do a full rebuild so new vocabulary terms are included
        all_docs = self.db.query(Document).all()
        if all_docs:
            self.build_full_index(all_docs)

    # ------------------------------------------------------------------
    # 3. Redis-first term lookup

    def get_index_from_cache(self, term: str) -> list[dict]:
        """
        Look up a term's document matches.
        Redis HIT  → return cached list of { doc_id, score }
        Redis MISS → query PostgreSQL, store result in Redis (TTL 24h)

        Returns:
            List of dicts: [{ "doc_id": str, "score": float }, ...]
        """
        cache_key = f"index:{term}"

        # --- Redis HIT ---
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # --- Redis MISS — query PostgreSQL ---
        rows = (
            self.db.query(IndexEntry)
            .filter(IndexEntry.term == term)
            .order_by(IndexEntry.tf_idf_score.desc())
            .all()
        )

        result = [{"doc_id": str(row.doc_id), "score": row.tf_idf_score} for row in rows]

        # Store in Redis with 24h TTL
        self.redis.setex(cache_key, REDIS_INDEX_TTL, json.dumps(result))

        return result

    # ------------------------------------------------------------------
    # 4. Persist full in-memory index to PostgreSQL

    def sync_to_postgres(self, docs: list[Document]) -> None:
        """
        Write all TF-IDF scores from the in-memory matrix to index_entries.
        Clears existing entries first (full rebuild scenario).
        """
        global _vectorizer, _doc_matrix, _doc_ids

        if _vectorizer is None or _doc_matrix is None:
            return

        # Clear existing index
        self.db.query(IndexEntry).delete()
        self.db.commit()

        feature_names = _vectorizer.get_feature_names_out()
        doc_id_map = {str(doc.id): str(doc.id) for doc in docs}

        cx = _doc_matrix.tocoo()
        batch = []

        for row_idx, col_idx, score in zip(cx.row, cx.col, cx.data):
            if score <= 0:
                continue
            doc_id = _doc_ids[row_idx]
            if doc_id not in doc_id_map:
                continue
            batch.append(IndexEntry(
                term=feature_names[col_idx],
                doc_id=doc_id,
                tf_idf_score=float(score),
                positions=None,
            ))

            # Flush in batches of 1000 to avoid memory spike
            if len(batch) >= 1000:
                self.db.bulk_save_objects(batch)
                self.db.commit()
                batch = []

        if batch:
            self.db.bulk_save_objects(batch)
            self.db.commit()

    # ------------------------------------------------------------------
    # 5. Internal — prime Redis from in-memory matrix after full build

    def _prime_redis_cache(self) -> None:
        """
        After a full index build, populate Redis for every term so the
        first search request is always a cache HIT.
        """
        global _vectorizer, _doc_matrix, _doc_ids

        if _vectorizer is None or _doc_matrix is None:
            return

        feature_names = _vectorizer.get_feature_names_out()
        cx = _doc_matrix.tocoo()

        # Group by term (col index)
        term_map: dict[int, list[dict]] = {}
        for row_idx, col_idx, score in zip(cx.row, cx.col, cx.data):
            if score <= 0:
                continue
            term_map.setdefault(col_idx, []).append({
                "doc_id": _doc_ids[row_idx],
                "score": round(float(score), 6),
            })

        pipe = self.redis.pipeline()
        for col_idx, matches in term_map.items():
            term = feature_names[col_idx]
            # Sort by score descending before caching
            matches.sort(key=lambda x: x["score"], reverse=True)
            pipe.setex(f"index:{term}", REDIS_INDEX_TTL, json.dumps(matches))
        pipe.execute()

    # ------------------------------------------------------------------
    # 6. Helper — get fitted vectorizer and doc matrix (used by SearchService)

    @staticmethod
    def get_vectorizer_and_matrix():
        """
        Returns the current in-memory vectorizer and document matrix.
        Used by SearchService to compute cosine similarity at query time.

        Returns:
            (TfidfVectorizer, sparse matrix, list[str]) or (None, None, [])
        """
        return _vectorizer, _doc_matrix, _doc_ids
    
    def build_index_from_db(self) -> None:
        """
        Load all documents from PostgreSQL and rebuild the in-memory
        TF-IDF index. Called on server startup to restore state after restart.
        """
        docs = self.db.query(Document).all()
        if docs:
            self.build_full_index(docs)
