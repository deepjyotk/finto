from pydantic import BaseModel, Field


class PortfolioQuery(BaseModel):
    """Outputs the final computation result of the user's query."""

    result: str = Field(
        ...,
        description="The final result of the portfolio query that was performed.",
    )
