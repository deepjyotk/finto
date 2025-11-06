from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class AgentMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Any] = None


class AgentResponse(BaseModel):
    messages: List[AgentMessage]
    final: str
    raw: Any
