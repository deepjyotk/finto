"""Core enums for the application."""

from enum import Enum
from typing import Any, Dict


class ChatMode(str, Enum):
    """Supported chat interaction modes."""

    OVERALL = "overall"
    PORTFOLIO = "portfolio"
    SCREENER = "screener"


CHAT_MODE_LABELS: dict["ChatMode", str] = {
    ChatMode.OVERALL: "Overall",
    ChatMode.PORTFOLIO: "Financial Analysis",
    ChatMode.SCREENER: "Screener",
}

CHAT_MODE_DESCRIPTIONS: dict["ChatMode", str] = {
    ChatMode.OVERALL: "Broad market and general finance context",
    ChatMode.PORTFOLIO: "Holdings, stock analysis, statements, and yfinance metrics",
    ChatMode.SCREENER: "Find and filter stocks by criteria",
}


class ThesysModel(Enum):
    """Supported Thesys models."""

    THESYS_CLAUDE_SONNET_4 = "c1/anthropic/claude-sonnet-4/v-20250617"
    THESYS_GPT_41 = "c1-exp/openai/gpt-4.1/v-20250617"


class LLMModel(Enum):
    """Supported AI models with associated LLM kwargs.

    Each enum member stores both the model name and its configuration kwargs.
    Access the model name with `.value['model']` or `.model_name`
    Access the kwargs with `.value['kwargs']` or `.llm_kwargs`
    Access the provider with `.value['provider']` or `.provider` (defaults to ``"openai"``).
    Access UI visibility with `.hide` (defaults to ``False``); members with ``hide: True`` are
    omitted from model pickers sent to the client.

    Auto — API / UI id ``"auto"``; use :meth:`resolve_to_openai_member` before
    calling OpenAI (maps to GPT-4o-mini). Graph context uses server defaults when Auto.

    **Switching models:** Pick a member and pass its ``model_name`` from the UI/API.
    GPT-5 / GPT-5.1 / GPT-5.4 often restrict ``temperature`` (many only allow ``1``). For a fast
    conversational GPT-5.1, use :attr:`GPT5p1ChatLatest` (``gpt-5.1-chat-latest``); for a
    pinned snapshot, use :attr:`GPT5p1Snapshot`. Frontier GPT-5.4 models are :attr:`GPT5p4`,
    :attr:`GPT5p4Pro`, :attr:`GPT5p4Mini`, and :attr:`GPT5p4Nano``.

    **Claude models** require ``ANTHROPIC_API_KEY`` in the environment.
    **Gemini models** require ``GOOGLE_API_KEY`` in the environment.
    """

    # Sentinel: user lets the app pick (see resolve_to_openai_member)
    Auto = {"model": "auto", "kwargs": {}}

    # GPT-3.5 Series
    GPT35Turbo = {"model": "gpt-3.5-turbo", "kwargs": {"temperature": 0}, "hide": True}
    GPT35Turbo16K = {
        "model": "gpt-3.5-turbo-16k",
        "kwargs": {"temperature": 0},
        "hide": True,
    }

    # GPT-4 Series
    GPT4 = {"model": "gpt-4", "kwargs": {"temperature": 0}, "hide": True}
    GPT4Turbo = {"model": "gpt-4-turbo", "kwargs": {"temperature": 0}, "hide": True}
    GPT4TurboPreview = {
        "model": "gpt-4-turbo-preview",
        "kwargs": {"temperature": 0},
        "hide": True,
    }
    GPT432K = {"model": "gpt-4-32k", "kwargs": {"temperature": 0}, "hide": True}

    # GPT-4o Series (Omni - multimodal)
    GPT4o = {"model": "gpt-4o", "kwargs": {"temperature": 0.5}, "hide": True}
    GPT4oMini = {"model": "gpt-4o-mini", "kwargs": {"temperature": 0}, "hide": True}
    GPT4o20240806 = {
        "model": "gpt-4o-2024-08-06",
        "kwargs": {"temperature": 0},
        "hide": True,
    }  # Dated version

    # GPT-4.1 Series
    GPT4p1 = {"model": "gpt-4.1", "kwargs": {"temperature": 0.5}}
    GPT4p1Mini = {"model": "gpt-4.1-mini", "kwargs": {"temperature": 0}}
    GPT4p1Nano = {"model": "gpt-4.1-nano", "kwargs": {"temperature": 0}, "hide": True}

    # GPT-5 Series (temperature: many GPT-5 models only accept 1 — see OpenAI model docs)
    GPT5 = {"model": "gpt-5", "kwargs": {}, "hide": True}
    GPT5Mini = {"model": "gpt-5-mini", "kwargs": {}, "hide": True}
    GPT5Nano = {"model": "gpt-5-nano", "kwargs": {}, "hide": True}
    GPT5Chat = {"model": "gpt-5-chat", "kwargs": {}, "hide": True}
    GPT5p1 = {"model": "gpt-5.1", "kwargs": {"temperature": 1}, "hide": True}
    GPT5p1Snapshot = {
        "model": "gpt-5.1-2025-11-13",
        "kwargs": {"temperature": 1},
        "hide": True,
    }
    # Conversational / "instant" style (documented alias for ChatGPT-style GPT-5.1)
    GPT5p1ChatLatest = {
        "model": "gpt-5.1-chat-latest",
        "kwargs": {"temperature": 1},
        "hide": True,
    }
    GPT5p1Instant = GPT5p1ChatLatest

    # GPT-5.4 Series (frontier — agentic, coding, professional workflows)
    GPT5p4 = {"model": "gpt-5.4", "kwargs": {"temperature": 1}}
    GPT5p4Pro = {"model": "gpt-5.4-pro", "kwargs": {"temperature": 1}, "hide": True}
    GPT5p4Mini = {"model": "gpt-5.4-mini", "kwargs": {"temperature": 1}}
    GPT5p4Nano = {"model": "gpt-5.4-nano", "kwargs": {"temperature": 1}}

    # GPT-5.2 Series (previous frontier; configurable reasoning effort on some endpoints)
    GPT5p2 = {"model": "gpt-5.2", "kwargs": {"temperature": 1}}
    GPT5p2Pro = {"model": "gpt-5.2-pro", "kwargs": {"temperature": 1}, "hide": True}

    # GPT-5 pro — higher-quality variant of GPT-5
    GPT5Pro = {"model": "gpt-5-pro", "kwargs": {"temperature": 1}, "hide": True}

    # ChatGPT "instant" style aliases (gpt-5.*-chat-latest on the models list)
    GPT5p3ChatLatest = {
        "model": "gpt-5.3-chat-latest",
        "kwargs": {"temperature": 1},
        "hide": True,
    }
    GPT5p2ChatLatest = {
        "model": "gpt-5.2-chat-latest",
        "kwargs": {"temperature": 1},
        "hide": True,
    }
    GPT5ChatLatest = {
        "model": "gpt-5-chat-latest",
        "kwargs": {"temperature": 1},
        "hide": True,
    }

    # O-Series (Reasoning Models - don't support temperature parameter)
    O1 = {"model": "o1", "kwargs": {}, "hide": True}
    O1Preview = {"model": "o1-preview", "kwargs": {}, "hide": True}
    O1Mini = {"model": "o1-mini", "kwargs": {}, "hide": True}
    O3 = {"model": "o3", "kwargs": {}}
    O3Pro = {"model": "o3-pro", "kwargs": {}, "hide": True}
    O4Mini = {"model": "o4-mini", "kwargs": {}, "hide": True}
    O4MiniHigh = {"model": "o4-mini-high", "kwargs": {}, "hide": True}

    # ── Claude (Anthropic) ─────────────────────────────────────────────────────
    # Latest generation (recommended for new projects)
    # Requires ANTHROPIC_API_KEY. Docs: https://platform.claude.com/docs/en/about-claude/models
    ClaudeOpus46 = {
        "model": "claude-opus-4-6",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeSonnet46 = {
        "model": "claude-sonnet-4-6",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeHaiku45 = {
        "model": "claude-haiku-4-5-20251001",
        "kwargs": {"temperature": 0},
        "provider": "anthropic",
        "hide": True,
    }

    # Previous Claude 4 generation (still available, not deprecated)
    ClaudeSonnet45 = {
        "model": "claude-sonnet-4-5-20250929",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeOpus45 = {
        "model": "claude-opus-4-5-20251101",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeOpus41 = {
        "model": "claude-opus-4-1-20250805",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeSonnet4 = {
        "model": "claude-sonnet-4-20250514",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }
    ClaudeOpus4 = {
        "model": "claude-opus-4-20250514",
        "kwargs": {"temperature": 0.5},
        "provider": "anthropic",
        "hide": True,
    }

    # ── Gemini (Google) ────────────────────────────────────────────────────────
    # Stable models (recommended for production)
    # Requires GOOGLE_API_KEY. Docs: https://ai.google.dev/gemini-api/docs/models
    Gemini25Pro = {
        "model": "gemini-2.5-pro",
        "kwargs": {"temperature": 0.5},
        "provider": "google",
        "hide": True,
    }
    Gemini25Flash = {
        "model": "gemini-2.5-flash",
        "kwargs": {"temperature": 0.5},
        "provider": "google",
        "hide": True,
    }
    Gemini25FlashLite = {
        "model": "gemini-2.5-flash-lite",
        "kwargs": {"temperature": 0},
        "provider": "google",
        "hide": True,
    }

    # Preview models (Gemini 3 series — may have stricter rate limits)
    Gemini31ProPreview = {
        "model": "gemini-3.1-pro-preview",
        "kwargs": {"temperature": 0.5},
        "provider": "google",
        "hide": True,
    }
    Gemini3FlashPreview = {
        "model": "gemini-3-flash-preview",
        "kwargs": {"temperature": 0.5},
        "provider": "google",
        "hide": True,
    }

    @property
    def model_name(self) -> str:
        """Get the model name string (``"auto"`` for :attr:`Auto`)."""
        return self.value["model"]

    @property
    def llm_kwargs(self) -> Dict[str, Any]:
        """Get the LLM kwargs dict."""
        return self.value["kwargs"]

    @property
    def provider(self) -> str:
        """Get the model provider (``"openai"``, ``"anthropic"``, or ``"google"``)."""
        return self.value.get("provider", "openai")  # type: ignore[return-value]

    @property
    def hide(self) -> bool:
        """If True, exclude from lists exposed to the frontend (still valid for API/config)."""
        return bool(self.value.get("hide", False))

    def resolve_to_openai_member(self) -> "LLMModel":
        """Map :attr:`Auto` to a concrete OpenAI-backed model; identity otherwise."""
        if self is LLMModel.Auto:
            return LLMModel.GPT4oMini
        return self

    def __str__(self) -> str:
        """Return the model name when converted to string."""
        return self.model_name

    def __repr__(self) -> str:
        """Return a representation of the enum member."""
        return f"<LLMModel.{self.name}: {self.model_name}>"

    @classmethod
    def from_model_name(cls, model_name: str) -> "LLMModel":
        """Get enum member by model name string."""
        # Old ids / typos → current model names (stored sessions, cached UI)
        legacy = {
            "gpt-5.1-instant": "gpt-5.1-chat-latest",
        }
        resolved = legacy.get(model_name, model_name)
        for member in cls:
            if member.model_name == resolved:
                return member
        raise ValueError(f"No LLMModel found with model name: {model_name}")


class ChatMessageType(str, Enum):
    """Enum for chat message types."""

    USER = "User"
    AI = "AI"


class Nodes:
    """Node name constants."""

    orchestrator = {
        "name": "orchestrator_node",
        "description": "Orchestrator node for routing between worker nodes.",
        "max_ai_messages_allowed": 60,
    }
    portfolio = {
        "name": "portfolio_node",
        "description": "Portfolio node for fetching portfolio information.",
        "max_ai_messages_allowed": 60,
    }
    code_execution = {
        "name": "code_execution_node",
        "description": "LLM node that generates and executes Python code for portfolio analysis.",
        "max_ai_messages_allowed": 60,
    }
    financial_analysis_worker_tools = {
        "name": "financial_analysis_tool_node",
        "description": "ToolNode that executes portfolio analysis tasks dispatched by the orchestrator.",
    }
    screener_analysis_worker_tools = {
        "name": "screener_analysis_tool_node",
        "description": "ToolNode that executes market-wide stock screening tasks dispatched by the orchestrator.",
    }
    web_search_worker_tools = {
        "name": "web_search_tool_node",
        "description": "ToolNode that executes web-search tasks dispatched by the orchestrator.",
    }
    final_response = {
        "name": "final_response_generation_node",
        "description": "Node that crafts the final answer from code execution output and the user request.",
        "max_ai_messages_allowed": 20,
    }
    unknown = {
        "name": "unknown_node",
        "description": "Unknown node for handling unknown queries.",
    }
