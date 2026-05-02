"""LLM-based screener intent classifier: maps user task → HITL form category."""

from __future__ import annotations

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory

logger = logger_for(__name__)

ScreenerIntentForm = Literal[
    "market_cap",
    "growth",
    "value",
    "dividend",
    "sector",
    "economic_sensitivity",
    "ownership",
    "investment_style",
    "volatility_risk",
]

_INTENT_DESCRIPTIONS: dict[str, str] = {
    "market_cap": "Screen by company size (large-cap >$10B, mid-cap $2B–$10B, small-cap <$2B).",
    "growth": "Find companies with strong revenue or earnings growth and high PEG tolerance.",
    "value": "Find companies trading at cheap valuation multiples (low P/E, PEG, P/B).",
    "dividend": "Find income-focused companies paying dividends with sustainable payout ratios.",
    "sector": "Filter companies by business sector, industry, or activity type.",
    "economic_sensitivity": "Classify stocks by economic cycle sensitivity: cyclical vs defensive, using beta.",
    "ownership": "Filter by country, exchange, listing type, or geographic market region.",
    "investment_style": "Screen by investment style: blue-chip, momentum, quality, value, or growth style.",
    "volatility_risk": "Screen by volatility and balance-sheet risk using beta, debt, and coverage ratios.",
}

_SYSTEM_PROMPT = """\
You are a stock screener intent classifier. Given a user's screening request, \
pick the single most relevant screener category from the list below.

Screener categories:
{categories}

Rules:
- Return ONLY the category key string exactly as listed above.
- If the request mentions company size (large, mid, small cap) → market_cap.
- If it mentions growth, revenue growth, earnings growth → growth.
- If it mentions undervalued, cheap, P/E, P/B, value investing → value.
- If it mentions dividends, income, yield, payout → dividend.
- If it mentions sector, industry, tech, healthcare, finance, etc. → sector.
- If it mentions cyclical, defensive, economic cycle, recession → economic_sensitivity.
- If it mentions country, exchange, US, India, domestic, international → ownership.
- If it mentions blue-chip, momentum, quality, investment style → investment_style.
- If it mentions volatility, beta, risk, leverage, debt coverage → volatility_risk.
- When unclear, default to market_cap.
"""

_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        ("human", "User screening request: {task}"),
    ]
)


class _IntentOutput(BaseModel):
    """Structured output for screener intent classification."""

    intent: ScreenerIntentForm


async def classify_screener_intent(
    task: str, llm_factory: LLMFactory
) -> ScreenerIntentForm:
    """Classify a screener task string into a supported HITL form category.

    Uses a small LLM chain with structured output.  Falls back to ``"market_cap"``
    on any error so the tool never hard-fails due to classification.
    """
    try:
        categories_text = "\n".join(
            f"  {key}: {desc}" for key, desc in _INTENT_DESCRIPTIONS.items()
        )
        llm = llm_factory(LLMModel.GPT4oMini)
        chain = _PROMPT_TEMPLATE | llm.with_structured_output(_IntentOutput)
        result: _IntentOutput = await chain.ainvoke(
            {"task": task, "categories": categories_text}
        )
        logger.info("Screener intent classified as %r for task: %.120s", result.intent, task)
        return result.intent
    except Exception as exc:
        logger.warning(
            "Screener intent classification failed (%s: %s); defaulting to 'market_cap'",
            type(exc).__name__,
            exc,
        )
        return "market_cap"
