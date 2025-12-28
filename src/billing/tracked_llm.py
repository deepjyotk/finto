"""Wrapper for LLMs that tracks token usage and deducts credits."""

from typing import Any, Optional
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.credit_manager import CreditManager
from src.core.json_logging import logger_for

logger = logger_for(__name__)


class InsufficientCreditsError(Exception):
    """Raised when user has insufficient credits for an operation."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient credits. Required: {required}, Available: {available}"
        )


class TrackedLLM:
    """Wrapper that tracks token usage and deducts credits automatically."""

    def __init__(
        self, 
        llm: BaseChatModel, 
        user_id: UUID | str,
        db_session: AsyncSession
    ):
        self.llm = llm
        self.user_id = user_id
        self.db_session = db_session
        self.model_name = getattr(llm, "model_name", str(llm.__class__.__name__))

    async def ainvoke(self, messages: Any, **kwargs) -> Any:
        """Async invoke LLM and track usage."""
        response = await self.llm.ainvoke(messages, **kwargs)
        await self._track_usage(response, kwargs)
        return response

    def invoke(self, messages: Any, **kwargs) -> Any:
        """Sync invoke - not recommended, use ainvoke instead."""
        raise NotImplementedError(
            "Sync invoke not supported with database credit tracking. Use ainvoke() instead."
        )
    
    async def _track_usage(self, response: Any, kwargs: dict):
        """Extract tokens and deduct credits."""
        # Extract token usage from response
        input_tokens = 0
        output_tokens = 0

        # OpenAI format
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

        # Anthropic format
        elif hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

        # Fallback: check for usage attribute
        elif hasattr(response, "usage"):
            usage = getattr(response, "usage", None)
            if usage:
                input_tokens = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0))
                output_tokens = getattr(
                    usage, "completion_tokens", getattr(usage, "output_tokens", 0)
                )

        if input_tokens > 0 or output_tokens > 0:
            credit_manager = CreditManager(self.user_id, self.db_session)
            success, credits, msg = await credit_manager.deduct_for_usage(
                model_name=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_id=kwargs.get("request_id"),
            )

            if not success:
                _, required_credits = credit_manager.calculate_cost(
                    self.model_name, input_tokens, output_tokens
                )
                raise InsufficientCreditsError(
                    required=required_credits, available=await credit_manager.get_balance()
                )

            logger.info(f"Tokens used: {input_tokens} in, {output_tokens} out. {msg}")
        else:
            logger.warning(f"Could not extract token usage from {self.model_name} response")

    def __getattr__(self, name: str) -> Any:
        """Delegate other method calls to the wrapped LLM."""
        return getattr(self.llm, name)
