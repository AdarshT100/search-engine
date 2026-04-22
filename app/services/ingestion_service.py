# Handles text extraction, document pipeline orchestration, and batch ingest logic.
"""
app/services/ingestion_service.py

Handles text extraction from uploaded files and document ingestion into
the database, inverted index, and S3 storage.

Raises ValueError (never HTTPException) — error translation is the API layer's job.
"""

import io
import uuid
import logging
from sqlalchemy.orm import Session

import fitz  # PyMuPDF

from app.core.nlp_pipeline import NLPPipeline
from app.services.index_service import IndexService
from app.data.s3_client import upload_file
from app.data.models import Document

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nlp = NLPPipeline()

    # ------------------------------------------------------------------   
    #  Text Extraction                                                     

    def extract_text_txt(self, file: bytes) -> str:
        """
        Decode raw TXT bytes as UTF-8.
        Raises ValueError if the result is empty after stripping whitespace.
        """
        try:
            text = file.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("TXT_DECODE_ERROR") from e

        if not text.strip():
            raise ValueError("EMPTY_DOCUMENT")

        return text

    def extract_text_pdf(self, file: bytes) -> str:
        """
        Extract the text layer from a digital PDF using PyMuPDF.
        Raises ValueError('SCANNED_PDF') if no text is found (scanned/image PDF).
        """
        try:
            pdf = fitz.open(stream=file, filetype="pdf")
        except Exception as e:
            raise ValueError("PDF_OPEN_ERROR") from e

        pages_text: list[str] = []
        for page in pdf:
            pages_text.append(page.get_text())
        pdf.close()

        full_text = "\n".join(pages_text)

        if not full_text.strip():
            raise ValueError("SCANNED_PDF")

        return full_text

    # ------------------------------------------------------------------ #
    #  Upload Ingestion                                                    

    def ingest_uploaded_file(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
    ) -> Document:
        """
        Full ingestion pipeline for a user-uploaded file:
          1. Detect extension and extract text
          2. Persist Document row to PostgreSQL
          3. Update inverted index via IndexService
          4. Upload raw file to S3 and store the key
          5. Return the committed Document ORM object

        Args:
            file_bytes: Raw bytes of the uploaded file.
            filename:   Original filename (used to detect .txt / .pdf).
            user_id:    UUID string of the authenticated user.

        Returns:
            The fully persisted Document ORM object.

        Raises:
            ValueError: With an error code string for known failure modes.
                        'UNSUPPORTED_FILE_TYPE' — extension is not .txt or .pdf
                        'TXT_DECODE_ERROR'      — TXT file is not valid UTF-8
                        'EMPTY_DOCUMENT'        — file contains no text after strip
                        'SCANNED_PDF'           — PDF has no extractable text layer
                        'PDF_OPEN_ERROR'        — PyMuPDF could not open the PDF
            RuntimeError: Propagated from S3 on upload failure.
        """
        # ── 1. Detect extension ───────────────────────────────────────── #
        lower_name = filename.lower()
        if lower_name.endswith(".txt"):
            ext = "txt"
        elif lower_name.endswith(".pdf"):
            ext = "pdf"
        else:
            raise ValueError("UNSUPPORTED_FILE_TYPE")

        # ── 2. Extract text ───────────────────────────────────────────── #
        if ext == "txt":
            raw_text = self.extract_text_txt(file_bytes)
        else:
            raw_text = self.extract_text_pdf(file_bytes)

        # ── 3. Preprocess through NLP pipeline ───────────────────────── #
        # (index_service.update_index re-runs this internally, but we
        #  validate here so an empty-after-preprocessing document is caught
        #  before any DB writes occur.)
        tokens = self.nlp.process(raw_text)
        if not tokens:
            raise ValueError("EMPTY_DOCUMENT")

        # ── 4. Persist Document to PostgreSQL ─────────────────────────── #
        # Use the original filename (without path) as the title.
        title = filename.rsplit("/", 1)[-1]

        doc = Document(
            title=title,
            body=raw_text,
            source="uploaded",
            s3_key=None,                    # filled in after S3 upload
            user_id=uuid.UUID(user_id),
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        logger.info("Document persisted: doc_id=%s user_id=%s", doc.id, user_id)

        # ── 5. Update inverted index ──────────────────────────────────── #
        # IndexService computes TF-IDF for this document incrementally and
        # invalidates the relevant Redis keys.
        try:
            IndexService(self.db).update_index(doc)
        except Exception as e:
            # Index failure is non-fatal for storage, but we log it clearly.
            logger.error("Index update failed for doc_id=%s: %s", doc.id, e)
            raise

        # ── 6. Upload raw file to S3 ──────────────────────────────────── #
        # RuntimeError from s3_client propagates directly to the API layer.
        s3_key = upload_file(io.BytesIO(file_bytes), ext)
        logger.info("S3 upload complete: key=%s", s3_key)

        # ── 7. Persist S3 key back to the document row ────────────────── #
        doc.s3_key = s3_key
        self.db.commit()

        return doc