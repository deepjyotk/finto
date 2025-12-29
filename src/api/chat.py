import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat import ChatRequest, ChatResponse
from src.billing.langsmith_tracker import CreditTrackingCallback
from src.core.db import get_session
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.core.schema import AgentMessage
from src.dependencies import get_chat_service
from src.services.chat import ChatService

logger = logger_for("api.chat")
router = APIRouter(prefix="/chat", tags=["chat"])

# !WARNING: this endpoing is only for testing purposes. It will be removed in the future.


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="Send a message to the chat system and receive a \
    response. Supports conversation history and optional file attachments.",
    deprecated=True,
)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """
    Process a chat message and return a response.

    - **message**: The user's message text (required)
    - **file**: Optional file identifier or path
    - **conversation_history**: List of previous messages for context

    Returns a chat response message.
    """

    thread_id = uuid.uuid4()
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        f"💬 Chat request started - User: {user_id}, Thread: {thread_id}, Message: {request.message[:50]}..."
    )

    # Create credit tracking callback
    credit_callback = CreditTrackingCallback(user_id, db)

    # Pass callback to service
    response = await chat_service.query(
        request, thread_id, user_id, db, callbacks=[credit_callback]
    )

    # If we received an AgentMessage, use its content; otherwise stringify
    if isinstance(response, AgentMessage):
        response_text = response.content
    elif response is None:
        response_text = ""
    else:
        response_text = str(response)

    logger.info(
        "chat_request",
        extra={
            "message_text": request.message,
            "has_file": bool(request.file),
            "conversation_history_length": len(request.conversation_history),
            "response_length": len(response_text) if isinstance(response_text, str) else None,
        },
    )

    # Log usage summary
    usage_summary = credit_callback.get_summary()
    logger.info(
        f"✅ Chat completed - "
        f"LLM calls: {usage_summary['llm_calls']}, "
        f"Tokens: {usage_summary['total_tokens']} "
        f"({usage_summary['total_input_tokens']} in / {usage_summary['total_output_tokens']} out), "
        f"Credits: {usage_summary['total_credits_deducted']}, "
        f"Cost: ${usage_summary['total_usd_spent']:.4f}"
    )

    # Log per-model breakdown
    for model, stats in usage_summary["model_breakdown"].items():
        logger.info(
            f"  └─ {model}: {stats['calls']} calls, "
            f"{stats['input_tokens']} in / {stats['output_tokens']} out = "
            f"{stats['credits']} credits (${stats['credits']/1000:.4f})"
        )

    # Log final balance
    try:
        from src.billing.credit_manager import CreditManager

        manager = CreditManager(user_id, db)
        balance = await manager.get_balance()
        logger.info(f"💰 Final balance: {balance} credits (${balance/1000:.2f})")
    except Exception as e:
        logger.warning(f"Failed to log credit balance: {e}")

    return ChatResponse(response=response_text)
