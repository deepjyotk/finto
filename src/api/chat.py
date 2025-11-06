from typing import List, Optional
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.utils.json_logging import logger_for
from .llm import query

logger = logger_for("api.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to send", examples=["Hello, how are you?"])
    file: Optional[str] = Field(None, description="Optional file path or identifier", examples=[None])
    conversation_history: List[str] = Field(
        default_factory=list,
        description="Previous messages in the conversation",
        examples=[["Hello", "Hi there!"]]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "What is the weather today?",
                "file": None,
                "conversation_history": ["Hello", "Hi! How can I help you?"],
            }
        }
    }


class ChatResponse(BaseModel):
    response: str = Field(..., description="AI response message", examples=["Hello! How can I help you?"])

    model_config = {
        "json_schema_extra": {"example": {"response": "Hello! How can I help you today?"}}
    }


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message to the chat system and receive a \
    response. Supports conversation history and optional file attachments.",
)
async def chat(request: ChatRequest):
    """
    Process a chat message and return a response.

    - **message**: The user's message text (required)
    - **file**: Optional file identifier or path
    - **conversation_history**: List of previous messages for context

    Returns a chat response message.
    """
    # Call the LLM query; run in a thread to avoid blocking the event loop
    response_text = await asyncio.to_thread(query, request.message)
    # Ensure non-None string for response model
    if response_text is None:
        response_text = ""
    else:
        response_text = str(response_text)
    logger.info(
        "chat_request",
        extra={
            "message_text": request.message,
            "has_file": bool(request.file),
            "conversation_history_length": len(request.conversation_history),
            "response_length": len(response_text) if isinstance(response_text, str) else None,
        },
    )
    return ChatResponse(response=response_text)
    