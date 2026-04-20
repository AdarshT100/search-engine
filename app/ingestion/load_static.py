# One-time script to load a static JSON dataset into PostgreSQL and build the index.
"""
app/ingestion/load_static.py

One-time ingestion script — loads the static JSON dataset into PostgreSQL
and builds the full TF-IDF index on server startup.

Expected JSON format:
[
    {
        "id":         "optional-string-or-omit",
        "title":      "Article Title",
        "body":       "Full article text...",
        "category":   "optional-string",
        "created_at": "optional ISO-8601 string"
    },
    ...
]

Usage (called from main.py on startup):
    from app.ingestion.load_static import ingest_static_dataset
    ingest_static_dataset(db, path="app/ingestion/data/static_articles.json")

Or run directly from the terminal to force a re-ingest:
    python -m app.ingestion.load_static
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.data.db import SessionLocal
from app.data.models import Document
from app.services.index_service import IndexService

logger = logging.getLogger(__name__)

# Default path to the static dataset JSON file
DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "static_articles.json"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ingest_static_dataset(
    db: Session,
    path: str | Path = DEFAULT_DATASET_PATH,
    force: bool = False,
) -> int:
    """
    Load static JSON articles into the documents table and build the full
    TF-IDF index.

    Args:
        db:    SQLAlchemy session.
        path:  Path to the JSON dataset file.
        force: If True, re-ingest even if static documents already exist.
               If False (default), skip ingestion when static docs are present.

    Returns:
        Number of documents ingested (0 if skipped).
    """
    path = Path(path)

    # --- Guard: skip if already ingested (unless forced) ---
    if not force:
        existing_count = (
            db.query(Document)
            .filter(Document.source == "static")
            .count()
        )
        if existing_count > 0:
            logger.info(
                "Static dataset already ingested (%d documents). "
                "Skipping. Pass force=True to re-ingest.",
                existing_count,
            )
            _rebuild_index_from_db(db)
            return 0

    # --- Load JSON file ---
    if not path.exists():
        logger.error("Static dataset not found at: %s", path)
        raise FileNotFoundError(f"Static dataset not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_articles = json.load(f)

    if not isinstance(raw_articles, list) or len(raw_articles) == 0:
        logger.warning("Static dataset is empty or not a JSON array. Nothing ingested.")
        return 0

    logger.info("Starting ingestion of %d articles from %s", len(raw_articles), path)

    # --- Parse and insert documents ---
    docs_to_insert = []
    skipped = 0

    for i, article in enumerate(raw_articles):
        title = article.get("title", "").strip()
        body = article.get("body", "").strip()

        if not title or not body:
            logger.warning("Article at index %d is missing title or body — skipped.", i)
            skipped += 1
            continue

        # Parse optional created_at; fall back to now
        created_at = _parse_datetime(article.get("created_at"))

        doc = Document(
            title=title,
            body=body,
            source="static",
            s3_key=None,
            user_id=None,
            created_at=created_at,
        )
        docs_to_insert.append(doc)

    if not docs_to_insert:
        logger.warning("No valid articles found after validation. Nothing ingested.")
        return 0

    # Bulk insert documents
    db.bulk_save_objects(docs_to_insert)
    db.commit()

    # Reload from DB to get auto-generated UUIDs
    inserted_docs = (
        db.query(Document)
        .filter(Document.source == "static")
        .all()
    )

    logger.info(
        "Inserted %d documents (%d skipped). Building TF-IDF index...",
        len(inserted_docs),
        skipped,
    )

    # --- Build full TF-IDF index ---
    index_service = IndexService(db)
    index_service.build_full_index(inserted_docs)

    logger.info(
        "Ingestion complete. %d documents indexed and searchable.",
        len(inserted_docs),
    )

    return len(inserted_docs)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rebuild_index_from_db(db: Session) -> None:
    """
    Load all static documents from PostgreSQL and rebuild the in-memory
    TF-IDF index + Redis cache. Called on server restart when documents
    are already present in the DB.
    """
    logger.info("Loading existing documents from DB to rebuild in-memory index...")

    all_docs = db.query(Document).all()

    if not all_docs:
        logger.warning("No documents found in DB. Index not built.")
        return

    index_service = IndexService(db)
    index_service.build_full_index(all_docs)

    logger.info(
        "In-memory index rebuilt from %d existing documents.", len(all_docs)
    )


def _parse_datetime(value: str | None) -> datetime:
    """
    Parse an ISO-8601 datetime string. Returns current UTC time if
    the value is missing or unparseable.
    """
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        logger.warning("Could not parse created_at value '%s' — using now().", value)
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CLI entry point — run directly to force re-ingest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    force_flag = "--force" in sys.argv
    dataset_path = DEFAULT_DATASET_PATH

    # Allow overriding path: python -m app.ingestion.load_static /path/to/data.json
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            dataset_path = Path(arg)
            break

    db: Session = SessionLocal()
    try:
        count = ingest_static_dataset(db, path=dataset_path, force=force_flag)
        if count > 0:
            print(f"✓ Ingested {count} documents successfully.")
        else:
            print("✓ Ingestion skipped (documents already present). Use --force to re-ingest.")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        db.close()
