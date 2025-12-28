"""LangSmith-based token tracking and credit deduction."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.credit_manager import CreditManager
from src.core.json_logging import logger_for

logger = logger_for(__name__)


class CreditTrackingCallback(BaseCallbackHandler):
    """Callback handler that tracks LLM token usage and deducts credits."""

    def __init__(self, user_id: UUID, db_session: AsyncSession):
        """Initialize the callback handler.
        
        Args:
            user_id: User UUID for credit deduction
            db_session: Database session for logging transactions
        """
        super().__init__()
        self.user_id = user_id
        self.db_session = db_session
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_credits_deducted = 0
        self.model_usage: Dict[str, Dict[str, int]] = {}
        self.llm_call_count = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes running. Collects data without async DB operations."""
        
        self.llm_call_count += 1
        
        # Extract token usage from LangSmith metadata
        llm_output = response.llm_output or {}
        
        # Try different token usage formats (OpenAI, Anthropic, Google)
        token_usage = (
            llm_output.get('token_usage') or 
            llm_output.get('usage') or 
            {}
        )
        
        # Extract tokens
        input_tokens = (
            token_usage.get('prompt_tokens') or 
            token_usage.get('input_tokens') or 
            0
        )
        output_tokens = (
            token_usage.get('completion_tokens') or 
            token_usage.get('output_tokens') or 
            0
        )
        
        if input_tokens == 0 and output_tokens == 0:
            logger.warning(
                f"⚠️ LLM call #{self.llm_call_count} returned no token usage data. "
                f"Response metadata: {llm_output}"
            )
            return
        
        # Extract model name
        model_name = (
            llm_output.get('model_name') or 
            llm_output.get('model') or 
            kwargs.get('invocation_params', {}).get('model_name') or
            kwargs.get('invocation_params', {}).get('model') or
            'unknown'
        )
        
        # Track totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # Track per-model (just accumulate data, don't write to DB yet)
        if model_name not in self.model_usage:
            self.model_usage[model_name] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'credits': 0,
                'calls': 0,
                'request_ids': []
            }
        
        self.model_usage[model_name]['input_tokens'] += input_tokens
        self.model_usage[model_name]['output_tokens'] += output_tokens
        self.model_usage[model_name]['calls'] += 1
        self.model_usage[model_name]['request_ids'].append(str(kwargs.get('run_id', '')))
        
        # Calculate credits (but don't deduct yet)
        credit_manager = CreditManager(self.user_id, self.db_session)
        _, credits = credit_manager.calculate_cost(model_name, input_tokens, output_tokens)
        self.total_credits_deducted += credits
        self.model_usage[model_name]['credits'] += credits
        
        logger.info(
            f"💳 LLM call #{self.llm_call_count} - "
            f"Model: {model_name}, Tokens: {input_tokens} in/{output_tokens} out, "
            f"Credits: {credits}"
        )
    
    async def finalize_and_save(self) -> None:
        """Write all accumulated usage to database after graph completes."""
        if self.total_credits_deducted == 0:
            return
        
        try:
            credit_manager = CreditManager(self.user_id, self.db_session)
            
            # Deduct total credits for all LLM calls
            for model_name, stats in self.model_usage.items():
                success, credits, msg = await credit_manager.deduct_for_usage(
                    model_name=model_name,
                    input_tokens=stats['input_tokens'],
                    output_tokens=stats['output_tokens'],
                    request_id=stats['request_ids'][0] if stats['request_ids'] else None
                )
                
                if not success:
                    logger.error(f"❌ Failed to deduct {credits} credits for {model_name}: {msg}")
                    
        except Exception as e:
            logger.error(f"❌ Error finalizing credit deductions: {e}", exc_info=True)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of token usage and credits deducted."""
        return {
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_input_tokens + self.total_output_tokens,
            'total_credits_deducted': self.total_credits_deducted,
            'total_usd_spent': self.total_credits_deducted / 1000,
            'llm_calls': self.llm_call_count,
            'model_breakdown': self.model_usage
        }
