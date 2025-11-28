"""Final response generation node that turns execution output into a user-facing answer."""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)


class FinalResponseGenerationNode:
    """Crafts the final response using the user request and execution output."""

    _PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
        """You are a financial assistant delivering the final answer.

User request:
{user_request}

Code execution output:
{execution_result}

Guidelines:
- Base your response ONLY on the execution output and the user request.
- Keep the answer concise and actionable; highlight key figures plainly.
- If the execution failed or looks incomplete, explain the issue and what is needed to fix it.
- Do not add extra analysis beyond what the output supports."""
    )

    def get_runnable_sequence(self):
        """Return runnable that produces the final user-facing response."""

        def final_response_generation_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            runtime = get_runtime(AgentContext)
            context = runtime.context
            model = context.get("portfolio_model", LLMModel.GPT4p1)
            llm_kwargs = {"model": model.model_name, **model.llm_kwargs}
            llm = ChatOpenAI(**llm_kwargs)

            user_request = (state.get("user_request") or "").strip() or "No user request provided."
            execution_result = (state.get("last_output") or "").strip()
            messages = state.get("messages", [])

            if not execution_result:
                fallback = "No code execution output was available to generate a final response."
                ai_msg = AIMessage(content=fallback, name="final_response_generation")
                return {
                    **state,
                    "messages": messages + [ai_msg],
                    "final_answer": fallback,
                    "done": True,
                }

            chain = self._PROMPT_TEMPLATE | llm
            ai_response = chain.invoke(
                {"user_request": user_request, "execution_result": execution_result}
            )
            final_answer = (
                ai_response.content if hasattr(ai_response, "content") else str(ai_response)
            )
            ai_msg = AIMessage(content=final_answer, name="final_response_generation")

            return {
                **state,
                "messages": messages + [ai_msg],
                "final_answer": final_answer,
                "done": True,
            }

        return RunnableLambda(final_response_generation_node_fn)
