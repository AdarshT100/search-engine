from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="user", passive_deletes=True
    )
    upload_logs: Mapped[list["UploadLog"]] = relationship(
        "UploadLog", back_populates="user"
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("source IN ('static', 'uploaded')", name="documents_source_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="documents")
    index_entries: Mapped[list["IndexEntry"]] = relationship(
        "IndexEntry", back_populates="document", passive_deletes=True
    )
    upload_logs: Mapped[list["UploadLog"]] = relationship(
        "UploadLog", back_populates="document"
    )


class IndexEntry(Base):
    __tablename__ = "index_entries"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    tf_idf_score: Mapped[float] = mapped_column(Float, nullable=False)
    positions: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="index_entries"
    )


class UploadLog(Base):
    __tablename__ = "upload_log"
    __table_args__ = (
        CheckConstraint("file_type IN ('pdf', 'txt')", name="upload_log_file_type_check"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    upload_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="upload_logs")
    document: Mapped["Document"] = relationship(
        "Document", back_populates="upload_logs"
    )