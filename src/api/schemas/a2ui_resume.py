"""Request body for POST /api/v1/a2ui/resume (HITL screener form submit)."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from src.core.enums import LLMModel


class A2UIResumeRequest(BaseModel):
    """Resume a paused LangGraph thread after a HITL interrupt (e.g. screener form)."""

    session_id: str = Field(description="Same as chat thread_id / session UUID string.")
    form_values: dict[str, Any] = Field(
        description="Field name → value map from a2ui-form-submit (aligned with form props names).",
    )
    broker_id: Optional[str] = Field(
        default=None,
        description="Optional broker scope; same semantics as C1ChatRequest.broker_id.",
    )
    model_payload: LLMModel = Field(
        default=LLMModel.Auto,
        description="Model selection for context rebuild on resume (same as /a2ui/chat).",
    )

    @field_validator("broker_id", mode="before")
    @classmethod
    def empty_broker_to_none(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip() or None

    @field_validator("model_payload", mode="before")
    @classmethod
    def coerce_model_payload(cls, v: Any) -> LLMModel:
        if isinstance(v, LLMModel):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s or s.lower() == "auto":
                return LLMModel.Auto
            return LLMModel.from_model_name(s)
        if isinstance(v, dict) and "model" in v:
            return LLMModel.from_model_name(str(v["model"]))
        raise ValueError(f"Invalid model_payload: {v!r}")
