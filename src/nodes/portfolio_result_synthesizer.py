import json
from typing import List
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel


class PortfolioResultSynthesizerNode:
    """Turns computed metrics into a concise final answer JSON."""

    def get_runnable_sequence(self, model: LLMModel):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a concise financial assistant. Produce ONLY JSON. The JSON must have a top-level key "
                    "'final_answer' with: summary (string) and details (array of objects each with keys 'symbol' (string) and 'profit' (number)). "
                    "No prose, no extra keys."
                ),
                ("user", "{computed_json}"),
            ]
        )
        llm = ChatOpenAI(model=model.value, temperature=0)

        # Guard: ensure only the intended variable is required by the prompt
        expected_vars = {"computed_json"}
        current_vars = set(getattr(prompt, "input_variables", []))
        if current_vars != expected_vars:
            prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "Produce ONLY JSON with key 'final_answer' containing 'summary' (string) and 'details' (list of {symbol, profit})."
                ),
                ("user", "{computed_json}"),
            ])

        def _input(msgs: List[BaseMessage]):
            computed = {}
            for m in reversed(msgs or []):
                if getattr(m, "name", "") == "computation":
                    try:
                        computed = json.loads(m.content) if isinstance(m.content, str) else m.content
                    except Exception:
                        computed = {"computed_metrics": m.content}
                    break
            return {"computed_json": json.dumps(computed)}

        def _wrap(ai_msg):
            return [AIMessage(content=ai_msg.content, name="result_synthesizer")]

        return RunnableLambda(_input) | (prompt | llm) | RunnableLambda(_wrap)
