import json
import uuid
from typing import Any, List, Optional
import numpy as np
from sqlalchemy import String, Text, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.models.base import Base, GUID, TimestampMixin
from app.core.config import settings


class CompatibleVector(TypeDecorator):
    """Vector type that cleanly stores and retrieves vector arrays across databases."""
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = settings.EMBEDDING_DIMENSION, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(JSON)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value.tolist()
        return [float(v) for v in value]

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return [float(v) for v in value.strip("[]()").split(",") if v.strip()]
        if isinstance(value, list):
            return [float(v) for v in value]
        return value


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="runbook")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    meta_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        CompatibleVector(settings.EMBEDDING_DIMENSION), nullable=True
    )
    meta_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_document_chunks_doc_chunk", "document_id", "chunk_index"),
    )
