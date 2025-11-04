from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from src.utils.json_logging import logger_for, setup_json_logging

setup_json_logging()
logger = logger_for("api.chat")
app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    file: str | None = None
    conversation_history: List[str] = []


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint that will be improved later.
    For now, it just returns 'hello'.
    """
    logger.info(
        "chat_request",
        extra={
            "message_text": request.message,
            "has_file": bool(request.file),
            "conversation_history_length": len(request.conversation_history),
        },
    )
    return ChatResponse(response="hello")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
