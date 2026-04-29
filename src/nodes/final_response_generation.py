"""Final response generation node that turns execution output into a user-facing answer."""

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

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory, ThesysChatOpenAI
from src.core.settings import thesys_settings
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)


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
                  "columns": [{{"key": string, "label": string, "format": "text"|"currency_inr"|"number"|"percentage"|"date"|"boolean"}}] | {{"path": "/json/pointer"}} (optional),
                  "rows": [{{"<column_key>": value, ...}}] | {{"path": "/json/pointer"}}
                }}
• SourceList props: {{
                  "sources": [{{"source": string, "title": string, "url": string (optional)}}] | {{"path": "/json/pointer"}},
                  "title": string | {{"path": "/json/pointer"}} (optional)
                }}
• Chart      props: {{
                  "chartType": "pie"|"bar"|"line"|"area",
                  "title": string | {{"path": "/json/pointer"}} (optional),
                  "data": [{{"name": string, "<value_key>": number, ...}}] | {{"path": "/json/pointer"}},
                  "series": [{{"key": string, "label": string (optional)}}] | {{"path": "/json/pointer"}} (optional),
                  "xKey": string | {{"path": "/json/pointer"}} (optional),
                  "unit": string | {{"path": "/json/pointer"}} (optional)
                }}

─── RULES ───
• Use official A2UI v0.9 messages: `createSurface`, `updateComponents`, and optionally `updateDataModel`.
• Use surfaceId "main" and catalogId "https://explainly.ai/catalogs/finance-chat-v1.json".
• The root component MUST have id "root".
• Every UI component must be a flat object inside the `updateComponents.components` array.
• Use short unique IDs: "title", "summary_row", "table1", "chart1", "info1", etc.
• Prefer putting repeated, tabular, or chart data inside `dataModel` and bind with `{{"path": "/..."}}`.
• For DataTable rows, use objects keyed by each column.key. Do not use positional row arrays unless the source data is already positional.
• For wide tabular data, DataTable can scroll horizontally. Still choose concise columns for each table:
  - Use one overview table with the most important columns.
  - Put separate detailed tables in Tabs when there are multiple table views such as All/Hold/Sell.
  - Avoid repeating the same large dataset in several full-width tables unless the user explicitly asked for every view.
• Do NOT put an entire markdown report into one Text component. Split content into structured A2UI components.
• Do NOT include markdown heading markers like "##" or emphasis wrappers like "*More:*" in Text values.
  Use Text variants (`h1`, `h2`, `h3`, `body`, `caption`) and separate components instead.
• For news or research summaries, create one Card per company/news item:
  - Card -> Column
  - Text h3 for the company/title
  - Text body for a concise 1-2 sentence summary
  - SourceList for sources, bound to dataModel whenever possible
  - InfoBox variant "warning" or "info" for missing/unavailable data
• Preserve source hyperlinks exactly when URLs are present in the data. Do not drop URLs into plain source text.
• Do NOT render news sources as several separate Text caption components. Use SourceList instead.
• SourceList source objects must use this shape: {{"source": "Reuters", "title": "Article title", "url": "https://..."}}.
  If the data has a source/title but no URL, include source and title without inventing a URL.
• Format all INR monetary values as "₹X,XXX.XX" (comma-separated, 2 decimal places) before placing them in the UI.
• Mark money columns with "format": "currency_inr" in DataTable columns.
• Mark quantity/count columns with "format": "number".
• Do NOT invent or modify data — use only the values provided below.
• Keep the hierarchy shallow and readable.
• For a success/error status in the data, add a Badge component.
• If the data contains tabular data, use DataTable — never render tables as plain text.
• If the user asks for a chart, pie, graph, or visualization → use Chart.
  - Use "pie" for distribution/breakdown by category (e.g. sector allocation).
  - Use "bar" for comparing values across categories.
  - Use "line" or "area" for trends over time.
  - For pie charts: the chart data must have "name" and one numeric value key (e.g. "value").
  - For INR pie/bar charts, set "unit": "₹".
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

            chain = prompt_template | llm
            ai_response = chain.invoke(
                {
                    "user_request": user_request,
                    "execution_result": execution_result,
                }
            )
            final_rendered_ui_answer = (
                ai_response.content if hasattr(ai_response, "content") else str(ai_response)
            )
            ai_msg = AIMessage(content=final_rendered_ui_answer, name="final_response_generation")

            history_message_length = context.get("history_message_length")
            if history_message_length is None:
                pruned_messages = [ai_msg]
            else:
                pruned_messages = self._prune_iteration_messages(
                    history_message_length, messages
                )
            return {
                **state,
                "messages": pruned_messages,
                "final_rendered_ui_answer": final_rendered_ui_answer,
                "done": True,
            }

        return RunnableLambda(final_response_generation_node_fn)
