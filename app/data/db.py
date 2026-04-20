# SQLAlchemy async session factory and database engine configuration.
"""
app/data/db.py
SQLAlchemy engine, session factory, and FastAPI dependency.
Exports: get_db (FastAPI dep) + SessionLocal (CLI / startup scripts).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings
 
settings = get_settings()
 
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # Reconnect if connection dropped
    pool_size=10,
    max_overflow=20,
)
 
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
 
 
def get_db():
    """
    FastAPI dependency — yields a DB session and closes it after the request.
    Usage in routes: db: Session = Depends(get_db)
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
