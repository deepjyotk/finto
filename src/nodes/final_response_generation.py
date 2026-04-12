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
    # The LLM generates a declarative A2UI component JSON payload that the React
    # client renders using its pre-approved catalog of native UI components.
    # Output must be ONLY valid JSON — no markdown fences, no explanations.
    _PROMPT_TEMPLATE_A2UI = ChatPromptTemplate.from_template(
        """You are a UI generation assistant for a financial portfolio application.
Given the data below, output ONLY a valid JSON object in the A2UI format described here.
Do NOT wrap the JSON in code fences. Do NOT add any explanation or text outside the JSON.

─── A2UI FORMAT ───
{{
  "type": "a2ui_response",
  "root": ["<id1>", "<id2>", ...],
  "components": {{
    "<id>": {{
      "type": "<component_type>",
      "props": {{ ... }},
      "children": ["<child_id>", ...]
    }}
  }}
}}

─── AVAILABLE COMPONENT TYPES ───
• "heading"      props: {{ "text": string, "level": 1|2|3 }}
• "badge"        props: {{ "text": string, "variant": "success"|"warning"|"error"|"info"|"neutral" }}
• "data-table"   props: {{
                   "columns": [{{"key": string, "label": string, "format": "text"|"currency_inr"|"number"|"percentage"}}],
                   "rows": [[...values in column order]]
                 }}
• "metric-card"  props: {{ "label": string, "value": string, "change": string (optional) }}
• "info-box"     props: {{ "text": string, "variant": "info"|"warning"|"success"|"error" }}
• "text"         props: {{ "content": string }}
• "divider"      props: {{}}
• "chart"        props: {{
                   "chart_type": "pie"|"bar"|"line"|"area",
                   "title": string (optional),
                   "data": [{{"name": string, "<value_key>": number, ...}}],
                   "data_keys": [string, ...] (keys to plot; omit to auto-detect),
                   "x_key": string (x-axis key for bar/line/area; default "name"),
                   "unit": string (prefix for tooltip values, e.g. "₹" or "%"; optional)
                 }}
• "form"         props: {{
                   "form_id": string (optional, DOM id; default: component id),
                   "title": string (optional heading inside the form),
                   "submit_label": string (optional; default "Submit"),
                   "children": [string, ...] — ids of child components (must be "form-field" entries).
                   Do NOT list child ids again in "root"; only the form id appears in "root".
                 }}
• "form-field"   props: {{
                   "name": string (required; HTML name + key in FormData on submit),
                   "label": string (visible label),
                   "input_type": "text" | "number",
                   "default": string | number (optional initial value),
                   "placeholder": string (optional),
                   "step", "min", "max": string (optional; for number inputs),
                   "help_text": string (optional small hint below the field)
                 }}

─── RULES ───
• Use short unique IDs: "h1", "badge1", "table1", "chart1", "info1", etc.
• Format all INR monetary values as "₹X,XXX.XX" (comma-separated, 2 decimal places).
• Mark money columns with "format": "currency_inr" in data-table columns.
• Mark quantity/count columns with "format": "number".
• Do NOT invent or modify data — use only the values provided below.
• Keep the hierarchy flat: prefer root-level components over deep nesting.
• For a success/error status in the data, add a badge component.
• If the data contains tabular data, use "data-table" — never render tables as plain text.
• If the user asks for a chart, pie, graph, or visualization → use "chart".
  - Use "pie" for distribution/breakdown by category (e.g. sector allocation).
  - Use "bar" for comparing values across categories.
  - Use "line" or "area" for trends over time.
  - For pie charts: data must have "name" and one numeric value key (e.g. "value").
  - For INR pie/bar charts, set "unit": "₹".
• You can include both a chart AND a data-table when both are useful.
• For user-editable parameters (screening thresholds, HITL tool args), use "form" with "form-field" children.
  Each field needs a unique "name" matching the API/tool parameter. Use "input_type": "number" for numeric thresholds.

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
                pruned_messages = self._prune_iteration_messages(messages, ai_msg)
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

            pruned_messages = self._prune_iteration_messages(
                context.get("history_message_length"), messages
            )
            return {
                **state,
                "messages": pruned_messages,
                "final_rendered_ui_answer": final_rendered_ui_answer,
                "done": True,
            }

        return RunnableLambda(final_response_generation_node_fn)
