import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAGSource(BaseModel):
    document_id: uuid.UUID
    document_title: str
    source: str
    chunk_id: uuid.UUID
    chunk_index: int
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language technical question")
    top_k: int = Field(5, ge=1, le=20, description="Number of most relevant chunks to retrieve")
    metadata_filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata key-value filters")
    doc_type: Optional[str] = Field(None, description="Optional filter by document type")


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[RAGSource]
    total_retrieved: int
    model: str
