from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

ai_router = APIRouter(prefix="/api/ai", tags=["ai"])


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None


class AiChatResponse(BaseModel):
    message: str
    model: str
    provider: str
    meta: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


@ai_router.post("/chat", response_model=AiChatResponse)
def chat_with_ai(request: AiChatRequest) -> AiChatResponse:
    raise NotImplementedError("AI assistant is deferred to Phase 2")


@ai_router.post("/chat/stream")
def chat_with_ai_stream(request: AiChatRequest):
    raise NotImplementedError("AI assistant is deferred to Phase 2")
