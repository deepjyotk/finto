from typing import Any, Optional

from pydantic import BaseModel


class AgentMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Any] = None
