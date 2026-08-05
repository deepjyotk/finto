"""Final response generation node that turns execution output into a user-facing answer."""

import json
from typing import List

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import get_runtime

from src.a2ui.v0_9 import parse_llm_surface_document
from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory, ThesysChatOpenAI
from src.core.settings import cloudflare_r2_settings, thesys_settings
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)

_A2UI_MAX_ATTEMPTS = 2
_A2UI_FALLBACK_DOCUMENT = json.dumps(
    {
        "messages": [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": "main",
                    "catalogId": "https://explainly.ai/catalogs/finance-chat-v1.json",
                    "sendDataModel": False,
                },
            },
            {
                "version": "v0.9",
                "updateComponents": {
                    "surfaceId": "main",
                    "components": [
                        {
                            "id": "root",
                            "component": "Column",
                            "children": ["err"],
                        },
                        {
                            "id": "err",
                            "component": "InfoBox",
                            "text": (
                                "The UI response could not be generated as valid JSON. "
                                "Please try the question again."
                            ),
                            "variant": "error",
                        },
                    ],
                },
            },
        ]
    },
    ensure_ascii=False,
)


class FinalResponseGenerationNode:
    """Crafts the final response using the user request and execution output."""

    def _prune_iteration_messages(
        self,
        history_message_length: int,
        messages: List[BaseMessage],
    ) -> List[BaseMessage]:
        """
        Prune the message history to keep only essential messages for the next iteration.

        Strategy:
        - Keep the FIRST HumanMessage (original user request for context)
        - Keep the FINAL AIMessage (the response we just generated)
        - Remove all intermediate messages (ToolMessages, AIMessages with tool_calls, etc.)

        This prevents token bloat and irrelevant tool context from polluting future iterations.

        Args:
            messages: Current message history
            final_ai_msg: The final AI response message to add

        Returns:
            List containing: final_ai_msg + RemoveMessage for all prunable messages
        """

        past_messages = messages[:history_message_length]

        if len(messages) > history_message_length:
            current_iteration_messages = messages[history_message_length:]
        else:
            current_iteration_messages = messages

        first_human_msg_id = None
        for msg in current_iteration_messages:
            if isinstance(msg, HumanMessage) and hasattr(msg, "id") and msg.id:
                first_human_msg_id = msg.id
                break

        last_ai_msg_id = None
        # reverse and get the last AIMessage
        for msg in reversed(current_iteration_messages):
            if isinstance(msg, AIMessage):
                last_ai_msg_id = msg.id
                break

        # remove all the messages: tool messages, ai messages with tool_calls, ai messages without tool_calls, system messages after first_human_msg_id and last_ai_msg
        messages_to_remove: List[RemoveMessage] = []

        for msg in past_messages:
            if (
                isinstance(msg, AIMessage)
                and getattr(msg, "tool_calls", None)
                and getattr(msg, "id", None)
            ):
                messages_to_remove.append(RemoveMessage(id=msg.id))
        for msg in current_iteration_messages:
            if msg.id != first_human_msg_id and msg.id != last_ai_msg_id:
                messages_to_remove.append(RemoveMessage(id=msg.id))
                continue
            if (
                isinstance(msg, ToolMessage)
                or (isinstance(msg, AIMessage) and (hasattr(msg, "tool_calls") and msg.tool_calls))
                or (isinstance(msg, AIMessage) and not hasattr(msg, "tool_calls"))
                or isinstance(msg, SystemMessage)
            ):
                if hasattr(msg, "id") and msg.id:
                    messages_to_remove.append(RemoveMessage(id=msg.id))
                    continue
            if isinstance(msg, HumanMessage) and msg.id != first_human_msg_id:
                if hasattr(msg, "id") and msg.id:
                    messages_to_remove.append(RemoveMessage(id=msg.id))
                    continue

        final_list_of_messages = (
            past_messages + current_iteration_messages + messages_to_remove
        )  # add the messages to remove to the current iteration messages

        logger.info(
            "Pruning iteration messages",
            extra={
                "history_message_length == len(past_messages) should be True": history_message_length
                == len(past_messages),
                "past_messages": len(past_messages),
                "current_iteration_messages": len(current_iteration_messages),
                "final_history_to_be_generated": len(final_list_of_messages)
                - 2 * len(messages_to_remove),
            },
        )
        return final_list_of_messages

    # Used when thesys_enabled=True: instructs the TheSys LLM to produce a C1 UI spec.
    _PROMPT_TEMPLATE_THESYS = ChatPromptTemplate.from_template(
        """Here's the final answer: {execution_result}

Here's the user_query: {user_request}

Without editing, changing, or tweaking anything in the final answer, your job is to generate a good Thesys UI to render the final_answer on the UI respecting the user's query."""
    )

    # Used when thesys_enabled=False (A2UI path).
    # The LLM generates official A2UI v0.9 server-to-client messages. The React
    # client processes them with MessageProcessor and renders A2uiSurface.
    # Output must be ONLY valid JSON — no markdown fences, no explanations.
    _PROMPT_TEMPLATE_A2UI = ChatPromptTemplate.from_template(
        """You are a UI generation assistant for a financial portfolio application.
Given the data below, output ONLY a valid JSON object containing official A2UI v0.9 server-to-client messages.
Do NOT wrap the JSON in code fences. Do NOT add any explanation or text outside the JSON.

─── OUTPUT FORMAT ───
{{
  "messages": [
    {{
      "version": "v0.9",
      "createSurface": {{
        "surfaceId": "main",
        "catalogId": "https://explainly.ai/catalogs/finance-chat-v1.json",
        "sendDataModel": false
      }}
    }},
    {{
      "version": "v0.9",
      "updateComponents": {{
        "surfaceId": "main",
        "components": [
          {{
            "id": "root",
            "component": "Column",
            "children": ["child-1"]
          }},
          {{
            "id": "child-1",
            "component": "Text",
            "text": {{"path": "/title"}},
            "variant": "h1"
          }}
        ]
      }}
    }},
    {{
      "version": "v0.9",
      "updateDataModel": {{
        "surfaceId": "main",
        "path": "/",
        "value": {{
          "title": "Example"
        }}
      }}
    }}
  ]
}}

─── AVAILABLE COMPONENTS ───
Built-in:
• Text       props: {{ "text": string | {{"path": "/json/pointer"}}, "variant": "h1"|"h2"|"h3"|"body"|"caption" }}
• Image      props: {{ "url": string | {{"path": "/json/pointer"}}, "description": string | {{"path": "/json/pointer"}} (optional), "fit": "contain"|"cover"|"fill"|"none"|"scaleDown" (optional), "variant": "icon"|"avatar"|"smallFeature"|"mediumFeature"|"largeFeature"|"header" (optional) }}
• Icon       props: {{ "name": "accountCircle"|"add"|"arrowBack"|"arrowForward"|"attachFile"|"calendarToday"|"call"|"camera"|"check"|"close"|"delete"|"download"|"edit"|"event"|"error"|"favorite"|"folder"|"help"|"home"|"info"|"mail"|"menu"|"moreVert"|"moreHoriz"|"notifications"|"payment"|"person"|"phone"|"photo"|"print"|"refresh"|"search"|"send"|"settings"|"share"|"shoppingCart"|"star"|"warning" }}
• Video      props: {{ "url": string | {{"path": "/json/pointer"}} }}
• AudioPlayer props: {{ "url": string | {{"path": "/json/pointer"}}, "description": string | {{"path": "/json/pointer"}} (optional) }}
• Column     props: {{ "children": ["child-id", ...], "justify": "start"|"center"|"end"|"spaceBetween"|"spaceAround"|"spaceEvenly"|"stretch" (optional), "align": "start"|"center"|"end"|"stretch" (optional) }}
• Row        props: {{ "children": ["child-id", ...], "justify": "start"|"center"|"end"|"spaceBetween"|"spaceAround"|"spaceEvenly"|"stretch" (optional), "align": "start"|"center"|"end"|"stretch" (optional) }}
• List       props: {{ "children": ["child-id", ...] | {{"path": "/items", "componentId": "template-id"}}, "direction": "vertical"|"horizontal" (optional), "align": "start"|"center"|"end"|"stretch" (optional) }}
• Card       props: {{ "child": "child-id" }}
• Tabs       props: {{ "tabs": [{{"title": string | {{"path": "/json/pointer"}}, "child": "child-id"}}] }}
• Divider    props: {{ "axis": "horizontal"|"vertical" (optional) }}

Custom finance catalog:
• Badge      props: {{ "text": string | {{"path": "/json/pointer"}}, "variant": "success"|"warning"|"error"|"info"|"neutral" }}
• MetricCard props: {{
                  "label": string | {{"path": "/json/pointer"}},
                  "value": string | {{"path": "/json/pointer"}},
                  "change": string | {{"path": "/json/pointer"}} (optional)
                }}
• InfoBox    props: {{ "text": string | {{"path": "/json/pointer"}}, "variant": "info"|"warning"|"success"|"error" }}
• DataTable  props: {{
                  "columns": [{{"key": string, "label": string, "format": "text"|"currency_inr"|"currency_usd"|"number"|"percentage"|"date"|"boolean"|"company_identity"}}] | {{"path": "/json/pointer"}} (optional),
                  "rows": [{{"<column_key>": value, ...}}] | {{"path": "/json/pointer"}}
                }}
                Note: "company_identity" format renders a logo image + "Company Name - SYMBOL" text inline in the cell.
                      Use it for every column that identifies a company (key = "company", "stock", etc.).
                Note: money formats — Indian stocks use "currency_inr" (₹); US stocks use "currency_usd" ($). Never mix.
                For large money values keep compact suffixes in the cell text (e.g. "$96.77B", "$409M") OR pass raw numbers;
                the UI preserves K/M/B/T and must never drop the magnitude suffix.
• SourceList props: {{
                  "sources": [{{"source": string, "title": string, "url": string (optional)}}] | {{"path": "/json/pointer"}},
                  "title": string | {{"path": "/json/pointer"}} (optional)
                }}
• Chart      props: {{
                  "chartType": "pie"|"bar"|"line"|"area"|"histogram",
                  "title": string | {{"path": "/json/pointer"}} (optional),
                  "data": [{{"<xKey>": string|number, "<seriesKey>": number|null, ...}}] | {{"path": "/json/pointer"}},
                  "series": [{{"key": string, "label": string (optional)}}] | {{"path": "/json/pointer"}} (optional),
                  "xKey": string | {{"path": "/json/pointer"}} (optional),
                  "xAxisLabel": string | {{"path": "/json/pointer"}} (REQUIRED for bar/line/area/histogram),
                  "yAxisLabel": string | {{"path": "/json/pointer"}} (REQUIRED for bar/line/area/histogram),
                  "unit": string | {{"path": "/json/pointer"}} (optional — "$" or "₹")
                }}
  Axis labels (MANDATORY for non-pie charts): clearly say what each axis means.
    Examples: xAxisLabel="Fiscal year end", yAxisLabel="Revenue (USD)"; xAxisLabel="Daily return bin", yAxisLabel="Number of days".
  Money scale: pass RAW numeric values (e.g. 96773000000). The UI formats Y-axis/tooltips as K/M/B/T (e.g. $96.8B).
    Do NOT expand money into long digit strings on the chart. Prefer keeping source K/M/B/T as numbers in the same scale, or full raw numbers.
  Multi-series line/area/bar (MANDATORY wide format):
    - One row per shared X value; each series is its own numeric key on that row.
    - Declare every series in "series" with human labels.
    - Prefer a shared category for X when comparing companies (e.g. "FY2023","FY2024") so lines connect cleanly.
    - If a series has no value at an X point, omit the key or set null — NEVER invent 0 or fabricate a year.
    - Fiscal calendars differ (e.g. NVDA FY ends ~Jan so "FY2026" can exist while TSLA calendar FY2026 is not filed yet).
      For comparison charts, prefer the overlapping years present for ALL series (drop years missing for any company),
      OR keep the union with nulls and state the gap in Text/InfoBox. Never invent Tesla/Nvidia values for a missing year.
    Correct:
      "xKey": "period",
      "xAxisLabel": "Fiscal year",
      "yAxisLabel": "Revenue (USD)",
      "series": [{{"key": "Tesla", "label": "Tesla"}}, {{"key": "Nvidia", "label": "Nvidia"}}],
      "data": [
        {{"period": "FY2023", "Tesla": 96773000000, "Nvidia": 60922000000}},
        {{"period": "FY2024", "Tesla": 97690000000, "Nvidia": 130497000000}}
      ]
    Wrong (interleaved single-series rows — lines look like disconnected dots):
      [{{"period": "2023-12-31", "Tesla": 96773000000}}, {{"period": "2024-01-31", "Nvidia": 60922000000}}]
  Histogram: use chartType "histogram" for distributions (returns, price bins, volume buckets).
  Send pre-binned rows: xKey = bin label (e.g. "-2% to -1%"), series key = frequency count (e.g. "count").
  Contiguous bins only — do not leave gaps in the bin axis. Example:
  {{"id": "ret_hist", "component": "Chart", "chartType": "histogram",
    "title": "Daily return distribution", "xKey": "bin",
    "xAxisLabel": "Daily return bin", "yAxisLabel": "Number of trading days",
    "series": [{{"key": "count", "label": "Days"}}],
    "data": [{{"bin": "-3% to -2%", "count": 4}}, {{"bin": "-2% to -1%", "count": 11}}, {{"bin": "-1% to 0%", "count": 28}}]}}

─── COMPANY IDENTITY FORMAT (MANDATORY) ───
The company logo CDN base URL is: {logo_cdn_base}
Logo URL pattern: {{logo_cdn_base}}/{{SYMBOL}}.png  (e.g. {logo_cdn_base}/RELIANCE.png or {logo_cdn_base}/TSLA.png)
Use the bare exchange ticker only (no ``.NS`` / ``.BO`` suffix). Prefer ``.png``; the UI also falls back to ``.svg`` / GCS if needed.

NEVER display a bare stock symbol (e.g. "RELIANCE") as a standalone label, column header, or Text value.
Whenever a company must be identified in the UI, apply the following rules:

1. In layout contexts (Card headers, List item headers, section titles, MetricCard labels):
   Use a Row with align "center" containing:
   • Image — url = "{logo_cdn_base}/{{SYMBOL}}.png", variant = "icon", description = "{{company_name}}"
   • Text  — text = "{{company_name}} - {{SYMBOL}}"

   Example for RELIANCE in a card header:
   {{"id": "reliance_header", "component": "Row", "children": ["reliance_logo", "reliance_title"], "align": "center"}},
   {{"id": "reliance_logo", "component": "Image", "url": "{logo_cdn_base}/RELIANCE.png", "variant": "icon", "description": "Reliance Industries Limited"}},
   {{"id": "reliance_title", "component": "Text", "text": "Reliance Industries Limited - RELIANCE"}}

2. In DataTable:
   • The column that identifies a company MUST use label = "Company" and format = "company_identity".
   • Row values for that column MUST be formatted as "{{company_name}} - {{SYMBOL}}" (e.g. "Reliance Industries Limited - RELIANCE").
   • The renderer extracts the symbol from that string to fetch and display the logo automatically.
   • Do NOT use label = "Symbol" or any bare symbol as a row value for the company column.

3. In List templates (using data model binding):
   Use the formatString function to compose logo URLs and labels dynamically:
   {{"id": "item_logo", "component": "Image",
     "url": {{"call": "formatString", "args": {{"value": "{logo_cdn_base}/${{symbol}}.png"}}}},
     "variant": "icon"}},
   {{"id": "item_label", "component": "Text",
     "text": {{"call": "formatString", "args": {{"value": "${{company_name}} - ${{symbol}}"}}}}}}

   where `symbol` and `company_name` are relative paths in the collection scope.

─── RULES ───
• JSON COMPLETENESS (CRITICAL): Output one COMPLETE, parseable JSON object. Never truncate mid-array/object.
  Forbidden: ``//`` comments, ``/* */``, ellipsis placeholders (``...``), ``truncated for brevity``,
  ``more rows available``, trailing commas, NDJSON, multiple top-level objects, or markdown fences.
  If a table is large, include at most the top 10 complete rows (still valid JSON) — never cut a row in half.
• FIDELITY: Present the execution data as-is. Do not rewrite, reinterpret, round, or "improve" answers. Keep compact suffixes like K/M/B/T unchanged (e.g. keep ``1M`` as ``1M`` — never expand to ``1,000,000``).
• Use official A2UI v0.9 messages: `createSurface`, `updateComponents`, and optionally `updateDataModel`.
• Use surfaceId "main" and catalogId "https://explainly.ai/catalogs/finance-chat-v1.json".
• The root component MUST have id "root".
• Every UI component must be a flat object inside the `updateComponents.components` array.
• Use short unique IDs: "title", "summary_row", "table1", "chart1", "info1", etc.
• Prefer putting repeated, tabular, or chart data inside `dataModel` and bind with `{{"path": "/..."}}`.
• For DataTable rows, the `rows` prop itself MUST be an array. Each row inside that array must be an object keyed by column.key.
  Correct (India / INR): `"rows": [{{"company": "Reliance Industries - RELIANCE", "profit": "₹1,000.00"}}]`.
  Correct (US / USD): `"rows": [{{"company": "Tesla, Inc. - TSLA", "profit": "$1,000.00"}}]`.
  Wrong: `"rows": {{"RELIANCE": {{"company": "Reliance Industries - RELIANCE", "profit": "₹1,000.00"}}}}`.
  Wrong: using ``$`` for Indian stocks or ``₹`` for US stocks.
  Do not use positional row arrays unless the source data is already positional.
• For wide tabular data, DataTable can scroll horizontally. Still choose concise columns for each table:
  - Use one overview table with the most important columns.
  - Put separate detailed tables in Tabs when there are multiple table views such as All/Hold/Sell.
  - Avoid repeating the same large dataset in several full-width tables unless the user explicitly asked for every view.
• Do NOT put an entire markdown report into one Text component. Split content into structured A2UI components.
• Do NOT include markdown heading markers like "##" or emphasis wrappers like "*More:*" in Text values.
  Use Text variants (`h1`, `h2`, `h3`, `body`, `caption`) and separate components instead.
• For news or research summaries, create one Card per company/news item:
  - Card -> Column
  - Company identity Row (logo + name) as the card header — see COMPANY IDENTITY FORMAT above
  - Text body for a concise 1-2 sentence summary
  - SourceList for sources, bound to dataModel whenever possible
  - InfoBox variant "warning" or "info" for missing/unavailable data
• Preserve source hyperlinks exactly when URLs are present in the data. Do not drop URLs into plain source text.
• Do NOT render news sources as several separate Text caption components. Use SourceList instead.
• SourceList source objects must use this shape: {{"source": "Reuters", "title": "Article title", "url": "https://..."}}.
  If the data has a source/title but no URL, include source and title without inventing a URL.
• CURRENCY (MANDATORY — never mix):
  - Indian stocks / INR amounts → mark DataTable money columns with "format": "currency_inr". Prefer compact "₹…" with K/M/B/T when large. Chart unit "₹".
  - US stocks / USD amounts → mark DataTable money columns with "format": "currency_usd". Prefer compact forms like "$96.77B" / "$409M" (never drop B/M/K/T). Chart unit "$".
  - Infer market from the data/symbols (e.g. TSLA/AAPL = USD; RELIANCE/TCS = INR). If a table mixes markets, either use pre-formatted money strings with the correct symbol per row, or split into separate INR and USD tables.
• Mark quantity/count columns with "format": "number".
• Do NOT invent or modify data — use only the values provided below (same numbers/text, including K/M/B/T forms).
• Keep the hierarchy shallow and readable.
• For a success/error status in the data, add a Badge component.
• If the data contains tabular data, use DataTable — never render tables as plain text.
• If the user asks for a chart, pie, graph, histogram, distribution, or visualization → use Chart (histogram for distributions).
  - Use "pie" for distribution/breakdown by category (e.g. sector allocation).
  - Use "bar" for comparing values across categories.
  - Use "line" or "area" for trends over time (multi-series wide format — see Chart props).
  - Always set xAxisLabel and yAxisLabel so axes are self-explanatory (except pie).
  - For pie charts: the chart data must have "name" and one numeric value key (e.g. "value").
  - For money charts: set "unit" to "₹" (INR) or "$" (USD); pass raw numbers — UI shows M/B.
• You can include both a Chart and a DataTable when both are useful.
• The client supports all standard Basic Catalog components, but final responses must be display-only.
• NEVER generate interactive input UI in final responses: no Button, TextField, CheckBox, ChoicePicker, Slider, DateTimeInput, or Modal.
• HITL parameter collection is handled by a deterministic server-side flow; final responses must be display-only components.

─── USER QUERY ───
{user_request}

─── DATA TO PRESENT ───
{execution_result}

Output ONLY the JSON object:"""
    )

    def __init__(self, llm_factory: LLMFactory):
        self._llm_factory = llm_factory

    @staticmethod
    def _message_text(response: object) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                else:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(content or "")

    @staticmethod
    def _validated_a2ui_json(raw: str) -> str | None:
        """Return a canonical ``{\"messages\": [...]}`` JSON string, or None if invalid."""
        messages, _persisted = parse_llm_surface_document(raw)
        if not messages:
            return None
        return json.dumps({"messages": messages}, ensure_ascii=False)

    def _generate_a2ui_json(
        self,
        *,
        llm,
        user_request: str,
        execution_result: str,
        logo_cdn_base: str,
    ) -> str:
        """Generate A2UI JSON; retry once if the model returns invalid/partial JSON."""
        prompt_messages = self._PROMPT_TEMPLATE_A2UI.format_messages(
            user_request=user_request,
            execution_result=execution_result,
            logo_cdn_base=logo_cdn_base,
        )
        last_raw = ""
        for attempt in range(1, _A2UI_MAX_ATTEMPTS + 1):
            if attempt == 1:
                ai_response = llm.invoke(prompt_messages)
            else:
                repair_messages = [
                    *prompt_messages,
                    AIMessage(content=last_raw),
                    HumanMessage(
                        content=(
                            "Your previous output was NOT valid complete JSON "
                            "(parse failed or document truncated). "
                            "Return ONLY one complete A2UI JSON object with a top-level "
                            '"messages" array. No markdown, no // comments, no ellipsis, '
                            "no truncated arrays. If a list is long, keep at most 10 full rows."
                        )
                    ),
                ]
                ai_response = llm.invoke(repair_messages)

            last_raw = self._message_text(ai_response)
            validated = self._validated_a2ui_json(last_raw)
            if validated is not None:
                if attempt > 1:
                    logger.info("A2UI JSON validated after repair attempt %s", attempt)
                return validated

            logger.warning(
                "A2UI JSON invalid on attempt %s (len=%s)",
                attempt,
                len(last_raw),
            )

        logger.error("A2UI JSON still invalid after %s attempts; using fallback UI", _A2UI_MAX_ATTEMPTS)
        return _A2UI_FALLBACK_DOCUMENT

    def get_runnable_sequence(self):
        """Return runnable that produces the final user-facing response."""

        def final_response_generation_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            runtime = get_runtime(AgentContext)
            context = runtime.context
            model = context.get("portfolio_model", LLMModel.GPT4p1)

            if thesys_settings.thesys_enabled:
                llm = ThesysChatOpenAI()
                prompt_template = self._PROMPT_TEMPLATE_THESYS
            else:
                llm = self._llm_factory(model)
                # Avoid streaming partial tokens into the A2UI client; we only emit
                # validated complete JSON via final_rendered_ui_answer / a2ui_message.
                if hasattr(llm, "model_copy"):
                    llm = llm.model_copy(update={"disable_streaming": True})
                prompt_template = self._PROMPT_TEMPLATE_A2UI

            user_request = (state.get("user_request") or "").strip() or "No user request provided."
            execution_result = (state.get("last_output") or "").strip()
            messages = state.get("messages", [])

            if not execution_result:
                fallback = "No code execution output was available to generate a final response."
                ai_msg = AIMessage(content=fallback, name="final_response_generation")
                history_message_length = context.get("history_message_length")
                if history_message_length is None:
                    pruned_messages = [ai_msg]
                else:
                    pruned_messages = self._prune_iteration_messages(
                        history_message_length,
                        [*messages, ai_msg],
                    )
                return {
                    **state,
                    "messages": pruned_messages,
                    "final_rendered_ui_answer": fallback,
                    "done": True,
                }

            if prompt_template is self._PROMPT_TEMPLATE_A2UI:
                cdn = (
                    cloudflare_r2_settings.public_domain
                    or "https://pub-02ae21b71a13498f94e99ef653d36c8a.r2.dev"
                ).rstrip("/")
                if not cdn.startswith("http"):
                    cdn = f"https://{cdn}"
                final_rendered_ui_answer = self._generate_a2ui_json(
                    llm=llm,
                    user_request=user_request,
                    execution_result=execution_result,
                    logo_cdn_base=cdn,
                )
            else:
                chain = prompt_template | llm
                ai_response = chain.invoke(
                    {
                        "user_request": user_request,
                        "execution_result": execution_result,
                    }
                )
                final_rendered_ui_answer = self._message_text(ai_response)

            ai_msg = AIMessage(content=final_rendered_ui_answer, name="final_response_generation")

            history_message_length = context.get("history_message_length")
            if history_message_length is None:
                pruned_messages = [ai_msg]
            else:
                pruned_messages = self._prune_iteration_messages(history_message_length, messages)
            return {
                **state,
                "messages": pruned_messages,
                "final_rendered_ui_answer": final_rendered_ui_answer,
                "done": True,
            }

        return RunnableLambda(final_response_generation_node_fn)
