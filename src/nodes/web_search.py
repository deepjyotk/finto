from datetime import datetime, timezone, timedelta
from typing import Final

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel
from src.schemas.web_search import WebSearchResult
from src.tools.tavily_web_search import tavily_web_search


class WebSearchNode:

    _SYSTEM_PROMPT_TEMPLATE: Final[
        str
    ] = """You are the Web Search Agent for a finance assistant.

Now (UTC): {today_utc_iso}
Now (IST, UTC+5:30): {today_ist_iso}

Mission
- Search once → synthesize immediately. Return concise summary + References URLs.

🚨 CRITICAL RULE - SINGLE TOOL CALL ONLY 🚨
1. Call tavily_web_search EXACTLY ONCE with your best query
2. After the tool responds, STOP and write your final answer immediately
3. DO NOT call the tool again, even if results seem incomplete
4. The tool returns 2 websites + AI summary—this is always sufficient

Output Format (REQUIRED)
After ONE tool call, return answer with:
- 2-4 bullets (≤100 words): key fact first, dates in IST/UTC, drivers
- "References:" section with 2 URLs from results

Domains to Prefer
- sebi.gov.in, nseindia.com, bseindia.com, reuters.com, economictimes.indiatimes.com, moneycontrol.com

Time Ranges
- "day"=today, "week"=7days, "month"=30days

Boundaries
- Never infer prices from articles—state "price data requires market-data tool"
- If results are thin, say so and cite best available sources"""

    def __init__(self):
        pass

    def _agent_prompt_template(self) -> ChatPromptTemplate:
        now_utc = datetime.now(timezone.utc).isoformat()
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", self._SYSTEM_PROMPT_TEMPLATE),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        complete_template = chat_template.partial(today_utc_iso=now_utc, today_ist_iso=now_ist)
        return complete_template

    def get_runnable_sequence(self, model: LLMModel) -> RunnableSequence:
        llm = ChatOpenAI(model=model.value, temperature=0)
        chain = self._agent_prompt_template() | llm.with_structured_output(WebSearchResult)

        # Convert WebSearchResult to AIMessage for MessageGraph compatibility
        return (
            RunnableLambda(lambda msgs: {"messages": msgs})
            | chain
            | RunnableLambda(lambda ws_result: [AIMessage(content=ws_result.answer)])
        )
