"""User-visible formatting for chat / LLM failures (streaming routes, logs stay detailed)."""


def looks_like_provider_billing_or_quota_error(message_lower: str) -> bool:
    """Detect credit/quota/billing style rejections from any LLM provider (heuristic)."""
    hints = (
        "credit balance is too low",
        "insufficient credits",
        "insufficient credit",
        "purchase credits",
        "plans & billing",
        "quota exceeded",
        "exceeded your quota",
        "exceeded your current quota",
        "billing to upgrade",
        "payment required",
    )
    if any(h in message_lower for h in hints):
        return True
    if "too low" in message_lower and "credit" in message_lower:
        return True
    if "upgrade" in message_lower and "credit" in message_lower:
        return True
    return False


def format_user_visible_chat_error(exc: BaseException) -> str:
    """Short, UI-safe markdown; full detail stays in server logs."""
    raw = str(exc)
    lower = raw.lower()

    if looks_like_provider_billing_or_quota_error(lower):
        return (
            "**Billing / quota:** The model provider rejected this request due to credits, "
            "quota, or billing on the API account. Open your provider’s billing or usage "
            "dashboard, add credits or adjust the plan, or switch to another model or API key "
            "in your app configuration."
        )

    if len(raw) > 600:
        return f"**Error:** {raw[:600]}…"
    return f"**Error:** {raw}"
