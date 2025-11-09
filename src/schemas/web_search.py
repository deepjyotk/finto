from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """Output schema for web search agent."""

    answer: str = Field(
        ...,
        description="Final answer with concise summary and References section with URLs",
    )
