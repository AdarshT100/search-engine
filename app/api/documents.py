# Route handlers for POST /upload, GET /documents, DELETE /documents/{id}.
"""
app/api/documents.py

Routes for document upload, listing, and deletion.
All endpoints require a valid JWT access token.

Error format: { "error": { "code": "...", "message": "...", "status": N } }
"""

import datetime
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_id
from app.data.db import get_db
from app.data.redis_client import get_redis
from app.data.s3_client import delete_file
from app.data.models import Document, UploadLog
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# ── Constants ──────────────────────────────────────────────────────────── #

MAX_FILE_SIZE = 5 * 1024 * 1024          # 5 MB in bytes
ALLOWED_MIME_TYPES = {"text/plain", "application/pdf"}
PDF_MAGIC = b"%PDF"                       # First 4 bytes of every valid PDF
DAILY_UPLOAD_LIMIT = 10


# ── Error helper ───────────────────────────────────────────────────────── #

def _error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "status": status_code}},
    )


# ── Redis rate-limit helpers ───────────────────────────────────────────── #

def _midnight_timestamp() -> int:
    """Return the Unix timestamp for midnight tonight (local server time, UTC)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    midnight = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(midnight.timestamp())


def _check_rate_limit(user_id: str) -> None:
    """Raise 429 if the user has already uploaded DAILY_UPLOAD_LIMIT files today."""
    redis = get_redis()
    key = f"ratelimit:upload:{user_id}"
    count = int(redis.get(key) or 0)
    if count >= DAILY_UPLOAD_LIMIT:
        raise _error(
            "RATE_LIMIT_EXCEEDED",
            "Upload limit of 10 per day reached.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _increment_rate_limit(user_id: str) -> None:
    """Increment today's upload counter and set it to expire at midnight."""
    redis = get_redis()
    key = f"ratelimit:upload:{user_id}"
    redis.incr(key)
    redis.expireat(key, _midnight_timestamp())


# ── Response models ────────────────────────────────────────────────────── #

class UploadResponse(BaseModel):
    doc_id: str
    title: str
    message: str


class DocumentItem(BaseModel):
    doc_id: str
    title: str
    file_type: str
    file_size: int
    uploaded_at: datetime.datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class DeleteResponse(BaseModel):
    message: str


# ── POST /api/documents/upload ─────────────────────────────────────────── #

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Any:
    """
    Upload a TXT or PDF file.
    The file is extracted, indexed via TF-IDF, stored on S3,
    and becomes searchable immediately.
    """

    # ── 1. Read file bytes ─────────────────────────────────────────────── #
    file_bytes = await file.read()

    # ── 2. Validate MIME type ──────────────────────────────────────────── #
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise _error(
            "INVALID_FILE_TYPE",
            "Only TXT and PDF files are supported.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # ── 3. Validate magic bytes ────────────────────────────────────────── #
    # Cross-check the declared MIME type against the actual file signature.
    # A file claiming to be application/pdf must start with %PDF.
    is_pdf_magic = file_bytes[:4] == PDF_MAGIC
    if content_type == "application/pdf" and not is_pdf_magic:
        raise _error(
            "INVALID_FILE_TYPE",
            "Only TXT and PDF files are supported.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    # If it has PDF magic bytes but was declared as text/plain, also reject.
    if content_type == "text/plain" and is_pdf_magic:
        raise _error(
            "INVALID_FILE_TYPE",
            "Only TXT and PDF files are supported.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # ── 4. Validate file size ──────────────────────────────────────────── #
    if len(file_bytes) > MAX_FILE_SIZE:
        raise _error(
            "FILE_TOO_LARGE",
            "File must be under 5MB.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # ── 5. Rate limit check ────────────────────────────────────────────── #
    _check_rate_limit(user_id)

    # ── 6. Ingest: extract → index → S3 → persist ─────────────────────── #
    filename = file.filename or "upload"
    try:
        doc = IngestionService(db).ingest_uploaded_file(
            file_bytes=file_bytes,
            filename=filename,
            user_id=user_id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "SCANNED_PDF":
            raise _error(
                "SCANNED_PDF",
                "Scanned PDFs are not supported in this version.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if code == "EMPTY_DOCUMENT":
            raise _error(
                "INVALID_FILE_TYPE",
                "The uploaded file contains no extractable text.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        # Any other ValueError (e.g. UNSUPPORTED_FILE_TYPE, TXT_DECODE_ERROR)
        raise _error(
            "INVALID_FILE_TYPE",
            "Only TXT and PDF files are supported.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except RuntimeError as exc:
        logger.error("S3 upload failure for user %s: %s", user_id, exc)
        raise _error(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ── 7. Write upload_log row ────────────────────────────────────────── #
    # file_size and file_type are available here at the route level.
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    log_entry = UploadLog(
        user_id=uuid.UUID(user_id),
        doc_id=doc.id,
        file_size=len(file_bytes),
        file_type=file_ext if file_ext in ("pdf", "txt") else "txt",
    )
    db.add(log_entry)
    db.commit()

    # ── 8. Increment rate limit counter ───────────────────────────────── #
    _increment_rate_limit(user_id)

    logger.info(
        "Upload complete: doc_id=%s user_id=%s size=%d",
        doc.id, user_id, len(file_bytes),
    )

    return UploadResponse(
        doc_id=str(doc.id),
        title=doc.title,
        message="Document indexed and searchable.",
    )


# ── GET /api/documents ─────────────────────────────────────────────────── #

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=DocumentListResponse,
)
def list_documents(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Any:
    """
    Return all documents uploaded by the authenticated user,
    joined with upload_log for file_size and file_type.
    """
    results = (
        db.query(
            Document.id,
            Document.title,
            UploadLog.file_type,
            UploadLog.file_size,
            UploadLog.upload_time,
        )
        .join(UploadLog, UploadLog.doc_id == Document.id)
        .filter(Document.user_id == uuid.UUID(user_id))
        .filter(Document.source == "uploaded")
        .order_by(Document.created_at.desc())
        .all()
    )

    return DocumentListResponse(
        documents=[
            DocumentItem(
                doc_id=str(row.id),
                title=row.title,
                file_type=row.file_type,
                file_size=row.file_size,
                uploaded_at=row.upload_time,
            )
            for row in results
        ]
    )


# ── DELETE /api/documents/{id} ─────────────────────────────────────────── #

@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_200_OK,
    response_model=DeleteResponse,
)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Any:
    """
    Delete a document the authenticated user owns.
    Removes the file from S3 and cascades index_entries deletion via FK.
    """

    # ── 1. Validate doc_id is a well-formed UUID ───────────────────────── #
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise _error(
            "DOC_NOT_FOUND",
            "Document not found or already deleted.",
            status.HTTP_404_NOT_FOUND,
        )

    # ── 2. Fetch document ──────────────────────────────────────────────── #
    doc = db.query(Document).filter(Document.id == doc_uuid).first()

    if doc is None:
        raise _error(
            "DOC_NOT_FOUND",
            "Document not found or already deleted.",
            status.HTTP_404_NOT_FOUND,
        )

    # ── 3. Ownership check ─────────────────────────────────────────────── #
    if doc.user_id is None or str(doc.user_id) != user_id:
        raise _error(
            "FORBIDDEN",
            "You do not have permission to delete this document.",
            status.HTTP_403_FORBIDDEN,
        )

    # ── 4. Delete from S3 ─────────────────────────────────────────────── #
    if doc.s3_key:
        try:
            delete_file(doc.s3_key)
        except RuntimeError as exc:
            # Log but do not abort — the DB row must still be cleaned up
            # to avoid orphaned references. S3 key can be audited separately.
            logger.error(
                "S3 delete failed for key=%s doc_id=%s: %s",
                doc.s3_key, doc_id, exc,
            )

    # ── 5. Delete document row (CASCADE cleans index_entries) ──────────── #
    db.delete(doc)
    db.commit()

    logger.info("Document deleted: doc_id=%s user_id=%s", doc_id, user_id)

    return DeleteResponse(message="Document deleted successfully.")