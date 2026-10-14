from datetime import datetime
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class DocumentModel(Base):
    """Relational model for ingested documents."""

    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunkModel.page_number",
    )

    def __repr__(self) -> str:
        return f"<DocumentModel doc_id={self.doc_id!r} total_chunks={self.total_chunks}>"


class DocumentChunkModel(Base):
    """Vector + relational model for chunked document fragments."""

    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    section_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["DocumentModel"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunkModel chunk_id={self.chunk_id!r} doc_id={self.doc_id!r} tokens={self.token_count}>"
