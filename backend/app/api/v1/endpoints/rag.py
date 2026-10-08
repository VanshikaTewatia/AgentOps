from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.rag.service import RAGService
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse

router = APIRouter()


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query internal knowledge base via RAG",
)
async def query_rag(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> RAGQueryResponse:
    service = RAGService(db)
    response = await service.query(
        query=request.query,
        top_k=request.top_k,
        metadata_filters=request.metadata_filters,
        doc_type=request.doc_type,
    )
    return response
