# FastAPI application entry point: creates the app instance and registers all routers.
"""
app/main.py
FastAPI application entry point.
Registers all routers and runs startup ingestion via lifespan.
"""
import logging
from contextlib import asynccontextmanager
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.core.config import get_settings
from app.data.db import SessionLocal
 
logger = logging.getLogger(__name__)
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: rebuild index from existing DB documents."""
    from app.ingestion.load_static import ingest_static_dataset
    from app.services.index_service import IndexService

    db = SessionLocal()
    try:
        # Load static dataset if JSON exists (silently skips if not found)
        ingest_static_dataset(db)
        print("STARTUP: static ingest done")

        # Always rebuild in-memory index from whatever is in the DB
        # This restores _vectorizer + _doc_matrix after every server restart
        logger.info("Rebuilding in-memory index from database...")
        index_svc = IndexService(db)
        print("STARTUP: IndexService created") #for debugging
        index_svc.build_index_from_db()
        print("STARTUP: build_index_from_db done") #for debugging
        logger.info("Index ready.")
    except Exception as e:
        import traceback
        print("Startup failed:", e)
        print(traceback.format_exc()) 
        # logger.error("Startup failed: %s", e)
    finally:
        db.close()
    yield
 
 
settings = get_settings()
 
app = FastAPI(
    title="Search Engine API",
    version="1.0.0",
    lifespan=lifespan,
)
 
# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
 
# Routers 
from app.api import auth, search, documents  # noqa: E402
 
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(documents.router)
 
 
@app.get("/health")
def health():
    return {"status": "ok"}
