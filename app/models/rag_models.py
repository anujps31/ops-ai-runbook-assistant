from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Question to ask the AI assistant"
    )


class RAGResponse(BaseModel):
    answer: str