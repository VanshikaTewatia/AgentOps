import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    meta_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    doc_type: str
    content_hash: str
    meta_info: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    chunks: Optional[List[DocumentChunkRead]] = None


class DocumentIngestRequest(BaseModel):
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Raw text content")
    source: str = Field(..., description="Source location or URI")
    doc_type: str = Field("runbook", description="Type of document, e.g. runbook, architecture, policy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata tags")


class DocumentIngestResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    source: str
    total_chunks: int
    message: str = "Document ingested and indexed successfully"
