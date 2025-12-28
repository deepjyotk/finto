"""Final response generation node that turns execution output into a user-facing answer."""

from langchain_core.messages import AIMessage
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

    _PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
        """You are a financial assistant delivering the final answer.

User request:
{user_request}

Analysis result or execution output:
{execution_result}

Guidelines:
- Base your response ONLY on the provided result/output and the user request.
- CRITICAL: If the execution output contains "=== SUGGESTED NEW METHOD ===" blocks, you MUST include them EXACTLY as shown in your response. Do NOT summarize or omit these technical suggestions.
- PRESERVE ALL STDOUT CONTENT including:
  * Method suggestions (=== SUGGESTED NEW METHOD === blocks)
  * Warnings about missing data
  * Calculation results
  * Any print() output from the code execution
- If the result is from code execution and looks incomplete or failed, explain the issue and what is needed to fix it.
- If the result is from news search, present it in a clear, well-formatted way with proper citations.
- Do not add extra analysis beyond what the output supports.
- FORMATTING METHOD SUGGESTIONS: When presenting method suggestions from "=== SUGGESTED NEW METHOD ===" blocks, format them as a developer suggestion box using markdown blockquote with emoji:
  
  > 🔧 **Developer Suggestion**
  > 
  > **Method:** `method_name`
  > 
  > **Signature:** `def method_name(params) -> return_type:`
  > 
  > **Steps:** Description of calculation steps
  > 
  > **Location:** Should be added to portfolio_metrics.py or portfolio_risk.py

{output_format_instructions}
"""
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

            llm = None
            output_format_instructions = ""
            if thesys_settings.thesys_enabled:
                llm = ThesysChatOpenAI()
            else:
                llm = self._llm_factory(model)
                output_format_instructions = """You must generate the final response in **valid Markdown** suitable for direct rendering in the UI.
                    Follow these rules strictly:

                    1. Use proper Markdown formatting at all times.
                    2. Structure the response for maximum readability on the UI.
                    3. Use:
                    - **Headings** to organize sections
                    - **Bold** and *italic* text for emphasis
                    - **Bullet lists** and **numbered lists** where appropriate
                    - **Tables** when presenting structured data
                    4. If providing code, wrap it in fenced code blocks (```).
                    5. Ensure the response is clean, well-formatted, and visually easy to scan.

                    Your output should feel polished, professional, and user-friendly.
                """
            user_request = (state.get("user_request") or "").strip() or "No user request provided."
            execution_result = (state.get("last_output") or "").strip()
            messages = state.get("messages", [])

            # If no execution result from code, check for news response in messages
            if not execution_result:
                # Look for the last AIMessage which might contain news search results
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage) and msg.content:
                        execution_result = msg.content
                        break

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
                {
                    "user_request": user_request,
                    "execution_result": execution_result,
                    "output_format_instructions": output_format_instructions,
                }
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
