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

    _PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
        """Here's the final answer: {execution_result}

Here's the user_query: {user_request}

Without editing, changing, or tweaking anything in the final answer, your job is to generate a good Thesys UI to render the final_answer on the UI respecting the user's query."""
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
            else:
                llm = self._llm_factory(model)
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

            chain = self._PROMPT_TEMPLATE | llm
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
