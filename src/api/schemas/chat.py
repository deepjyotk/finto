"""Chat API request and response schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field

from src.core.enums import LLMModel


class ChatRequest(BaseModel):
    message: str = Field(
        ..., description="User message to send", examples=["Hello, how are you?"]
    )
    file: Optional[str] = Field(
        None, description="Optional file path or identifier", examples=[None]
    )
    conversation_history: List[str] = Field(
        default_factory=list,
        description="Previous messages in the conversation",
        examples=[["Hello", "Hi there!"]],
    )
    model: LLMModel = Field(
        default=LLMModel.GPT4p1,
        description="AI model to use for the chat",
        examples=[LLMModel.GPT4p1],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "What is the weather today?",
                "file": None,
                "conversation_history": ["Hello", "Hi! How can I help you?"],
                "model_name": "gpt-4o-mini",
            }
        }
    }


class ChatResponse(BaseModel):
    response: str = Field(
        ..., description="AI response message", examples=["Hello! How can I help you?"]
    )

    model_config = {
        "json_schema_extra": {
            "example": {"response": "Hello! How can I help you today?"}
        }
    }
