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
    """Startup: ingest static dataset and build index."""
    from app.ingestion.load_static import ingest_static_dataset
    db = SessionLocal()
    try:
        ingest_static_dataset(db)
    except Exception as e:
        logger.error("Startup ingestion failed: %s", e)
    finally:
        db.close()
    yield  # Server runs here
    # Shutdown logic (if any) goes here
 
 
settings = get_settings()
 
app = FastAPI(
    title="Search Engine API",
    version="1.0.0",
    lifespan=lifespan,
)
 
# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
 
# ── Routers ───────────────────────────────────────────────────────────────
from app.api import auth, search, documents  # noqa: E402
 
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(documents.router)
 
 
@app.get("/health")
def health():
    return {"status": "ok"}
