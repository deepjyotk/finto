from datetime import datetime, timedelta, timezone
from typing import Any, Final, Literal

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.schemas.agent_state import AgentContext, AgentState
from src.schemas.web_search import WebSearchResult

logger = logger_for(__name__)


def _format_tavily_for_llm(search_result: Any, max_chars: int = 4000) -> str:
    """Turn Tavily output into prompt-safe text without json.dumps (responses may
    contain non-JSON-serialisable values such as exception objects).
    """
    if search_result is None:
        return "(No search results.)"
    if isinstance(search_result, str):
        return search_result[:max_chars]
    if not isinstance(search_result, dict):
        return str(search_result)[:max_chars]

    parts: list[str] = []
    q = search_result.get("query")
    if q is not None:
        parts.append(f"Query: {q}")
    ans = search_result.get("answer")
    if ans is not None:
        parts.append(f"AI summary: {str(ans)[:1500]}")

    for i, r in enumerate(search_result.get("results") or [], 1):
        if isinstance(r, dict):
            title = str(r.get("title", ""))[:300]
            url = str(r.get("url", ""))
            content = str(r.get("content", ""))[:800]
            parts.append(f"\n[{i}] {title}\n    URL: {url}\n    {content}")
        else:
            parts.append(f"\n[{i}] {str(r)[:500]}")

    text = "\n".join(parts).strip()
    return text[:max_chars] if text else "(Empty search payload.)"


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

    def __init__(self, llm_factory: LLMFactory):
        self._llm_factory = llm_factory

    def _agent_prompt_template(self) -> ChatPromptTemplate:
        now_utc = datetime.now(timezone.utc).isoformat()
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", self._SYSTEM_PROMPT_TEMPLATE),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        complete_template = chat_template.partial(
            today_utc_iso=now_utc, today_ist_iso=now_ist
        )
        return complete_template

    def create_worker_tool(self):
        """Build a self-contained web-search LangChain tool for the orchestrator.

        Calls Tavily directly then uses the LLM to synthesise a concise summary with
        source citations.  The orchestrator passes a focused task string; this tool
        returns the synthesised answer as plain text.
        """

        @tool
        async def web_search_tool(
            task: str,
            time_range: Literal["day", "week", "month", "year"] = "week",
            search_depth: Literal["basic", "advanced"] = "basic",
            max_results: int = 3,
        ) -> str:
            """Search for financial news, market updates, NSE/SEBI/BSE circulars,
            earnings announcements, and macro/policy headlines.

            Use for: news, headlines, market updates, circulars, announcements,
            regulatory filings, macro events, earnings results.

            Args:
                task: The specific search query, e.g.
                      'Latest news for RELIANCE, TCS, INFY' or
                      'SEBI circulars on F&O margin rules this week'.
                time_range: Recency filter for results.
                    - "day"   → breaking news / today only
                    - "week"  → last 7 days (default; good for most queries)
                    - "month" → last 30 days (use for trend/regulatory research)
                    - "year"  → last 12 months (use for broad historical context)
                search_depth: Controls crawl thoroughness.
                    - "basic"    → fast, headline-level results (default)
                    - "advanced" → deep crawl with richer content — use only for
                                   broad research queries where detail matters
                max_results: Number of sources to retrieve, 1–5 (default 3).
                    - Use 1–2 for targeted single-stock lookups
                    - Use 4–5 for broad market sweeps or multi-stock queries
            """
            from src.tools.tavily_web_search import tavily_web_search as _tavily

            try:
                search_result = await _tavily.ainvoke(
                    {
                        "query": task,
                        "time_range": time_range,
                        "search_depth": search_depth,
                        "max_results": max_results,
                    }
                )
            except Exception as exc:
                logger.exception("web_search_tool: Tavily search failed")
                return (
                    f"Web search failed: {exc!s}. Try a shorter query or retry later."
                )

            # Format and return Tavily results for the orchestrator
            results_text = _format_tavily_for_llm(search_result)
            return results_text

        return web_search_tool

    def get_runnable_sequence(self) -> RunnableSequence:
        prompt = self._agent_prompt_template()

        def web_search_node_fn(state: AgentState) -> AgentState:
            # Access AgentContext via runtime
            runtime = get_runtime(AgentContext)
            context = runtime.context
            web_search_model = context.get("web_search_model", LLMModel.GPT4oMini)

            llm = self._llm_factory(web_search_model)
            chain = prompt | llm.with_structured_output(WebSearchResult)

            messages = state.get("messages", [])
            ws_result = chain.invoke({"messages": messages})
            ai_msg = AIMessage(content=ws_result.answer)
            return {
                **state,
                "messages": messages + [ai_msg],
            }

        return RunnableLambda(web_search_node_fn)
