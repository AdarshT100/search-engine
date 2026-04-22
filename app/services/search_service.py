# Business logic for query preprocessing, TF-IDF scoring, and ranked result retrieval.
"""
app/services/search_service.py

Handles query preprocessing, index lookup, TF-IDF re-scoring,
snippet generation, and pagination for the search endpoint.

Dependencies:
    - IndexService  (app.services.index_service)
    - NLPPipeline   (app.core.nlp_pipeline)
    - Document ORM  (app.data.models)
    - get_db        (app.data.db)
"""

from __future__ import annotations

import math
from typing import Optional

from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.core.nlp_pipeline import NLPPipeline
from app.data.models import Document
from app.services.index_service import IndexService

# ---------------------------------------------------------------------------
# Constants

RESULTS_PER_PAGE = 10
SNIPPET_LENGTH = 150

class SearchService:
    """
    Orchestrates the full search pipeline:
      1. Preprocess query tokens via NLPPipeline
      2. Look up each token in the Redis/PostgreSQL inverted index
      3. Merge candidate doc_ids with OR logic, deduplicate
      4. Re-score via cosine similarity against the live TF-IDF matrix
      5. Apply optional source filter
      6. Sort, paginate, fetch Document rows, generate snippets
      7. Return a structured dict matching the API Contract §2 shape
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._nlp = NLPPipeline()

    # ------------------------------------------------------------------
    # Public interface

    def search(
        self,
        query: str,
        page: int = 1,
        source_filter: Optional[str] = None,
    ) -> dict:
        """
        Execute a full search and return a paginated result dict.

        Args:
            query:         Raw user query string (already length-validated by router).
            page:          1-based page number.
            source_filter: Optional 'static' or 'uploaded' filter.

        Returns:
            {
                query, page, total_results, total_pages,
                results: [ { doc_id, title, snippet, score, source, created_at } ]
            }
        """
        # ── Step 1: Preprocess query ───────────────────────────────────
        tokens: list[str] = self._nlp.process(query)

        if not tokens:
            return self._empty_response(query, page)

        # ── Step 2: Fetch candidate doc_ids from index cache ──────────
        # Each call returns list[{doc_id: str, score: float}]
        # Merge with OR logic; keep the highest per-token score per doc.
        index_svc = IndexService(self.db)
        candidate_scores: dict[str, float] = {}  # doc_id -> best cache score

        for token in tokens:
            matches = index_svc.get_index_from_cache(token)
            for entry in matches:
                doc_id = entry["doc_id"]
                score = entry["score"]
                if doc_id not in candidate_scores or score > candidate_scores[doc_id]:
                    candidate_scores[doc_id] = score

        if not candidate_scores:
            return self._empty_response(query, page)

        candidate_ids: list[str] = list(candidate_scores.keys())

        # ── Step 3: Re-score via cosine similarity ─────────────────────
        # get_vectorizer_and_matrix() is a @staticmethod — no db needed.
        vectorizer, doc_matrix, doc_ids = IndexService.get_vectorizer_and_matrix()

        scored: dict[str, float] = {}  # doc_id -> final cosine score

        if vectorizer is not None and doc_matrix is not None and doc_ids:
            # Transform the preprocessed query into the existing vocabulary space.
            # Join tokens back to a string so TfidfVectorizer can tokenize it.
            query_str = " ".join(tokens)
            query_vec = vectorizer.transform([query_str])  # (1, n_features)

            # Build a boolean mask for candidate doc_ids that exist in the matrix.
            id_to_row: dict[str, int] = {did: i for i, did in enumerate(doc_ids)}
            rows, valid_ids = [], []
            for did in candidate_ids:
                if did in id_to_row:
                    rows.append(id_to_row[did])
                    valid_ids.append(did)

            if rows:
                candidate_matrix = doc_matrix[rows]          # (k, n_features)
                sims = cosine_similarity(query_vec, candidate_matrix)[0]  # (k,)
                for did, sim in zip(valid_ids, sims):
                    scored[did] = float(sim)

            # For candidates not present in the live matrix, fall back to cache score.
            for did in candidate_ids:
                if did not in scored:
                    scored[did] = candidate_scores[did]
        else:
            # Index not yet built (e.g. cold start with no docs) — use cache scores.
            scored = {did: candidate_scores[did] for did in candidate_ids}

        # ── Step 4: Fetch Document rows & apply source filter ──────────
        doc_id_list = list(scored.keys())

        query_obj = self.db.query(Document).filter(Document.id.in_(doc_id_list))
        if source_filter:
            query_obj = query_obj.filter(Document.source == source_filter)

        documents: list[Document] = query_obj.all()

        if not documents:
            return self._empty_response(query, page)

        # ── Step 5: Sort — score DESC, created_at DESC for ties ────────
        def sort_key(doc: Document):
            return (-(scored.get(str(doc.id), 0.0)), -doc.created_at.timestamp())

        documents.sort(key=sort_key)

        # ── Step 6: Paginate ───────────────────────────────────────────
        total_results = len(documents)
        total_pages = math.ceil(total_results / RESULTS_PER_PAGE)
        page = max(1, min(page, total_pages))  # clamp to valid range
        offset = (page - 1) * RESULTS_PER_PAGE
        page_docs = documents[offset : offset + RESULTS_PER_PAGE]

        # ── Step 7: Build result dicts with snippets ───────────────────
        results = []
        for doc in page_docs:
            doc_id_str = str(doc.id)
            results.append(
                {
                    "doc_id": doc_id_str,
                    "title": doc.title,
                    "snippet": self._generate_snippet(doc.body, tokens),
                    "score": round(scored.get(doc_id_str, 0.0), 4),
                    "source": doc.source,
                    "created_at": doc.created_at.isoformat(),
                }
            )

        return {
            "query": query,
            "page": page,
            "total_results": total_results,
            "total_pages": total_pages,
            "results": results,
        }

    # ------------------------------------------------------------------
    # Private helpers

    def _generate_snippet(self, body: str, tokens: list[str]) -> str:
        """
        Return a 150-character excerpt from *body* centred around the first
        occurrence of any query token (case-insensitive).

        Falls back to the first 150 characters if no token is found.
        """
        body_lower = body.lower()
        best_pos = len(body)  # sentinel

        for token in tokens:
            pos = body_lower.find(token)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        if best_pos == len(body):
            # No token found — use the beginning of the body.
            return body[:SNIPPET_LENGTH].strip()

        # Centre the window around the match; stay within bounds.
        half = SNIPPET_LENGTH // 2
        start = max(0, best_pos - half)
        end = start + SNIPPET_LENGTH

        if end > len(body):
            end = len(body)
            start = max(0, end - SNIPPET_LENGTH)

        snippet = body[start:end].strip()

        # Add ellipsis markers where we've cut mid-document.
        if start > 0:
            snippet = "..." + snippet
        if end < len(body):
            snippet = snippet + "..."

        return snippet

    @staticmethod
    def _empty_response(query: str, page: int) -> dict:
        return {
            "query": query,
            "page": page,
            "total_results": 0,
            "total_pages": 0,
            "results": [],
        }