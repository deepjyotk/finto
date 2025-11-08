from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class RouteQuery(BaseModel):
    """Route a user query to the most relevant route."""

    decision: Literal["computation", "analysis"] = Field(
        ...,
        description="Given a user question choose to route it to computation or analysis.",
    )


decision_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a helpful AI assistant that decides whether to use the computation or "
                "analysis node based on stock and portfolio questions. The computation node "
                "handles current stock prices, gains, returns, and related calculations. The "
                "analysis node covers portfolio summaries, holdings, and counts from the Excel "
                "file. For each user question, choose the appropriate route: 'computation' or "
                "'analysis'."
            ),
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
decision_chain = decision_prompt | llm.with_structured_output(RouteQuery)

raw = decision_chain.invoke(
    {
        "messages": [HumanMessage(content="What are the total number of stocks in my portfolio?")],
    }
)

# Validate/convert the raw result into the RouteQuery model to satisfy type checkers
try:
    # Pydantic v2
    result: RouteQuery = RouteQuery.model_validate(raw)  # type: ignore[arg-type]
except Exception:
    # Fallback: cast for static type checkers if validation isn't available
    from typing import cast

    result = cast(RouteQuery, raw)

print("Decision Chain Result:", result.decision)
