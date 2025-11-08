from pydantic import BaseModel, Field


class ComputationQuery(BaseModel):
    """Outputs the final computation result of the user's query."""

    computation: str = Field(
        ...,
        description="The final result of the computation that was performed.",
    )
