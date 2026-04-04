import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from thesys_genui_sdk.context import write_content, write_custom_markdown
from thesys_genui_sdk.fast_api import with_c1_response

# with_c1_response() returns HTTP 200 + SSE immediately and runs the handler in a
# background task. Raising HTTPException does not change the status code on the wire
# (the client already got 200). Surface failures by streaming an error via C1.

from src.api.schemas.thesys_chat import (
    C1ChatRequest,
    ChatMetadataResponse,
    ChatModeItem,
    LLMModelItem,
    SessionItem,
    SessionMessageConfig,
    SessionResponse,
    SessionsListResponse,
    UserBrokerItem,
)
from src.core.chat_errors import format_user_visible_chat_error
from src.core.enums import CHAT_MODE_DESCRIPTIONS, ChatMode, LLMModel
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_holdings_service, get_thesys_chat_service
from src.services.chat_thesys_service import ThesysChatService
from src.services.holdings import HoldingsService

logger = logger_for("api.thesys_chat")
router = APIRouter(prefix="/thesys", tags=["thesys-chat"])


@router.post(
    "/session",
    summary="Create a new chat session",
    description="Creates a new chat session for the authenticated user and returns the session ID.",
    response_model=SessionResponse,
)
async def create_session(
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Create a new chat session for the authenticated user.
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "create_session_request",
        extra={
            "user_id": str(user_id),
        },
    )

    chat_session = await thesys_chat_service.create_session(user_id)

    return SessionResponse(
        session_id=chat_session.session_id,
        started_at=chat_session.started_at,
    )


@router.get(
    "/session",
    summary="Get chat sessions for the authenticated user (paginated)",
    description=(
        "Returns past chat sessions for the authenticated user, sorted by most recent first. "
        "Supports optional pagination via page and page_limit query parameters. "
        "If not provided, defaults to page=1 and page_limit=10. Maximum page_limit is 100."
    ),
    response_model=SessionsListResponse,
)
async def get_sessions(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number (1-indexed). Optional, defaults to 1.",
    ),
    page_limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of sessions per page. Optional, defaults to 10. Maximum is 100.",
    ),
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Get all chat sessions for the authenticated user, sorted by creation date (most recent first).

    Pagination is optional:
    - If page and page_limit are not provided, defaults to page=1 and page_limit=10
    - Uses database-level pagination (LIMIT/OFFSET) for efficient querying
    - Returns pagination metadata including total_sessions, total_pages, and has_next_page
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "get_sessions_request",
        extra={
            "user_id": str(user_id),
            "page": page,
            "page_limit": page_limit,
        },
    )

    # Get paginated sessions from service (which uses DB-level pagination)
    sessions, total_sessions = await thesys_chat_service.get_user_sessions(
        user_id, page=page, page_limit=page_limit
    )

    # Calculate pagination metadata
    total_pages = (
        (total_sessions + page_limit - 1) // page_limit if total_sessions > 0 else 0
    )
    has_next_page = page < total_pages

    return SessionsListResponse(
        sessions=[
            SessionItem(
                session_id=session.session_id,
                started_at=session.started_at,
            )
            for session in sessions
        ],
        page=page,
        page_limit=page_limit,
        total_sessions=total_sessions,
        total_pages=total_pages,
        has_next_page=has_next_page,
    )


@router.get(
    "/session/{session_id}",
    summary="Get messages for a specific session",
    description="Returns all messages for a given session ID, ordered by sequence number.",
    response_model=SessionMessageConfig,
)
async def get_session(
    session_id: str,
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Get all messages for a specific chat session.
    """
    user_id = uuid.UUID(user["user_id"])
    session_uuid = uuid.UUID(session_id)

    logger.info(
        "get_session_request",
        extra={
            "session_id": session_id,
            "user_id": str(user_id),
        },
    )

    return await thesys_chat_service.get_session_messages(session_uuid, user_id)


@router.delete(
    "/session/{session_id}",
    summary="Delete a chat session",
    description="Deletes a chat session and all its associated messages. Only the owner of the session can delete it.",
)
async def delete_session(
    session_id: str,
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Delete a chat session and all its associated messages.

    This endpoint deletes the chat session and all messages associated with it.
    Only the owner of the session can delete it.
    """
    user_id = uuid.UUID(user["user_id"])
    session_uuid = uuid.UUID(session_id)

    logger.info(
        "delete_session_request",
        extra={
            "session_id": session_id,
            "user_id": str(user_id),
        },
    )

    try:
        await thesys_chat_service.delete_session(session_uuid, user_id)
        logger.info(
            "delete_session_success",
            extra={
                "session_id": session_id,
                "user_id": str(user_id),
            },
        )
        return {"message": "Session deleted successfully"}
    except ValueError as e:
        logger.error(
            "delete_session_error",
            extra={
                "session_id": session_id,
                "user_id": str(user_id),
                "error": str(e),
            },
        )
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            "delete_session_error",
            extra={
                "session_id": session_id,
                "user_id": str(user_id),
                "error": str(e),
            },
        )
        raise HTTPException(status_code=500, detail=f"Error deleting session: {str(e)}")


@router.get(
    "/chat_metadata",
    summary="Get chat metadata for the authenticated user",
    description="Returns brokers, available chat modes, and available LLM models.",
    response_model=ChatMetadataResponse,
)
async def get_chat_metadata(
    holdings_service: HoldingsService = Depends(get_holdings_service),
    user: dict = Depends(require_auth),
):
    """
    Get chat metadata for the authenticated user.

    Returns brokers, all available chat modes, and all available LLM models.
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "get_chat_metadata_request",
        extra={
            "user_id": str(user_id),
        },
    )

    brokers = await holdings_service.repo.get_user_brokers(user_id)

    chat_modes = [
        ChatModeItem(
            id=mode.value,
            label=mode.name.capitalize(),
            description=CHAT_MODE_DESCRIPTIONS[mode],
        )
        for mode in ChatMode
    ]

    llm_models = [
        LLMModelItem(
            id=model.model_name,
            label="Auto" if model is LLMModel.Auto else model.model_name.upper(),
        )
        for model in LLMModel
        if not model.hide
    ]

    return ChatMetadataResponse(
        brokers=[
            UserBrokerItem(broker_id=b["broker_id"], broker_name=b["broker_name"])
            for b in brokers
        ],
        chat_modes=chat_modes,
        llm_models=llm_models,
    )


@router.post(
    "/chat",
    summary="Streaming Thesys C1 chat endpoint",
    description=(
        "Streaming endpoint consumed by the Thesys C1Chat React component. "
        "It receives prompt, sessionId, and responseId and forwards the "
        "conversation to the C1 model, streaming tokens back as SSE."
    ),
)
@with_c1_response()
async def thesys_chat(
    request: C1ChatRequest,
    thesys_chat_service: ThesysChatService = Depends(get_thesys_chat_service),
    user: dict = Depends(require_auth),
):
    """
    Dedicated Thesys endpoint for <C1Chat> with automatic credit tracking.
    """
    user_id = uuid.UUID(user["user_id"])

    logger.info(
        "thesys_chat_request",
        extra={
            "session_id": request.session_id,
            "user_id": str(user_id),
        },
    )

    # Manually create db session to keep it open during graph execution
    from src.billing.langsmith_tracker import CreditTrackingCallback
    from src.core.db import SessionLocal

    db = SessionLocal()
    try:
        credit_callback = CreditTrackingCallback(user_id, db)

        agent_message = await thesys_chat_service.query(
            request, user_id=user_id, callbacks=[credit_callback]
        )

        # Now finalize and save credit deductions to database
        await credit_callback.finalize_and_save()

        # Log usage summary
        usage_summary = credit_callback.get_summary()
        logger.info(
            f"✅ Thesys chat completed - "
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
                f"{stats['credits']} credits (${stats['credits'] / 1000:.4f})"
            )

        # Log final balance
        try:
            from src.billing.credit_manager import CreditManager

            manager = CreditManager(user_id, db)
            balance = await manager.get_balance()
            logger.info(f"💰 Final balance: {balance} credits (${balance / 1000:.2f})")
        except Exception as e:
            logger.warning(f"Failed to log credit balance: {e}")

        if agent_message and agent_message.content:
            await write_content(agent_message.content)
    except Exception as e:
        logger.error(f"Error in thesys_chat: {e}", exc_info=True)
        await write_custom_markdown(format_user_visible_chat_error(e))
    finally:
        await db.close()
