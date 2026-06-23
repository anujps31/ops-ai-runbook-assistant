from fastapi import APIRouter

from app.models.rag_models import (
    RAGRequest,
    RAGResponse
)

from app.services.rag_service import RAGService

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["RAG"]
)

rag_service = RAGService()


@router.post(
    "/ask",
    response_model=RAGResponse
)
async def ask_question(
    request: RAGRequest
):

    answer = rag_service.ask(
        request.question
    )

    return RAGResponse(
        answer=answer
    )