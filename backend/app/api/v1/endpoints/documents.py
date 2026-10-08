import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.document_repository import DocumentRepository
from app.rag.service import DocumentIngestionService
from app.rag.chunking import extract_text_from_bytes
from app.schemas.document import (
    DocumentRead,
    DocumentIngestRequest,
    DocumentIngestResponse,
)

router = APIRouter()


@router.post(
    "/ingest",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw text document",
)
async def ingest_document(
    request: DocumentIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> DocumentIngestResponse:
    service = DocumentIngestionService(db)
    response = await service.ingest_document(
        title=request.title,
        content=request.content,
        source=request.source,
        doc_type=request.doc_type,
        metadata=request.metadata,
    )
    return response


@router.post(
    "/upload",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a file (.txt, .md, .pdf)",
)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: str = Form("runbook"),
    db: AsyncSession = Depends(get_db),
) -> DocumentIngestResponse:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extracted_content = extract_text_from_bytes(file_bytes, file.filename or "unknown.txt")
    if not extracted_content.strip():
        raise HTTPException(status_code=400, detail="Could not extract readable text from uploaded file.")

    service = DocumentIngestionService(db)
    doc_title = title or (file.filename or "Uploaded Document")

    response = await service.ingest_document(
        title=doc_title,
        content=extracted_content,
        source=f"upload://{file.filename}",
        doc_type=doc_type,
        metadata={"filename": file.filename, "content_type": file.content_type},
    )
    return response


@router.get(
    "",
    response_model=List[DocumentRead],
    summary="List all indexed knowledge documents",
)
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    doc_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[DocumentRead]:
    repo = DocumentRepository(db)
    docs = await repo.list_documents(limit=limit, offset=offset, doc_type=doc_type)
    return docs


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get document details and its chunks",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    repo = DocumentRepository(db)
    doc = await repo.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document with ID {document_id} not found.")
    return doc
