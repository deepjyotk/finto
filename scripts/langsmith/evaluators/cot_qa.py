"""LangSmith CoT QA evaluation for the LangGraph agent."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Mapping
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.schemas import Example, Run
from pydantic import BaseModel, Field

from src.core.enums import LLMModel
from src.graph import Graph

DATASET_NAME = "finto-qa-dataset-1"
DEFAULT_MODEL = LLMModel.GPT4oMini


@lru_cache(maxsize=1)
def _get_compiled_graph(model: LLMModel):
    """Compile and cache the LangGraph for reuse during evaluation."""
    return Graph.get_graph(model)


def _message_content_to_str(message: Any) -> str:
    """Normalize message content to plain text for scoring."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        normalized_chunks: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                normalized_chunks.append(str(chunk.get("text") or chunk.get("content") or ""))
            else:
                normalized_chunks.append(str(chunk))
        return "\n".join(normalized_chunks).strip()
    return str(content)


def _extract_answer(graph_result: Any) -> str:
    """Extract the assistant's final answer from the LangGraph output."""
    if isinstance(graph_result, dict):
        messages = graph_result.get("messages") or []
        if messages:
            return _message_content_to_str(messages[-1])
    if isinstance(graph_result, list) and graph_result:
        return _message_content_to_str(graph_result[-1])
    return str(graph_result or "")


def predict_agent_answer(
    inputs: Mapping[str, Any], config: RunnableConfig | None = None, **_: Any
) -> Dict[str, str]:
    """Invoke the LangGraph agent on a dataset row."""
    question = inputs.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Each dataset example must include a non-empty 'question'.")

    graph = _get_compiled_graph(DEFAULT_MODEL)

    run_config: RunnableConfig = {}
    if config:
        run_config.update(config)
    configurable = dict(run_config.get("configurable", {}))
    configurable.setdefault("thread_id", str(uuid4()))
    run_config["configurable"] = configurable

    graph_state = {"messages": [HumanMessage(content=question.strip())]}
    context = {"user_id": uuid4()}
    result = graph.invoke(graph_state, config=run_config, context=context)

    return {"answer": _extract_answer(result)}


class CotQAGrade(BaseModel):
    """Structured result returned by the grading LLM."""

    score: float = Field(description="1.0 for correct answers, 0.0 for incorrect", ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief rationale explaining the score.")


_cot_qa_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a meticulous evaluator for financial Q&A agents. "
                "Given the original user question, the assistant's answer, and the reference answer, "
                "decide if the assistant fully matches the reference. "
                "Return JSON with fields 'score' (1 for correct, 0 for incorrect) and 'reasoning'."
            ),
        ),
        (
            "human",
            (
                "Question:\n{question}\n\n"
                "Assistant Answer:\n{prediction}\n\n"
                "Reference Answer:\n{reference}\n"
                "Is the assistant answer fully correct compared to the reference?"
            ),
        ),
    ]
)

_cot_qa_chain = _cot_qa_prompt | ChatOpenAI(model=DEFAULT_MODEL.value, temperature=0).with_structured_output(
    CotQAGrade
)


def cot_qa_evaluator(run: Run, example: Example, **_: Any) -> Dict[str, Any]:
    """Grade the agent answer using the CoT QA evaluator chain."""
    outputs = run.outputs or {}
    prediction = outputs.get("answer", "")
    reference = (example.outputs or {}).get("answer", "")
    question = (example.inputs or {}).get("question", "")

    if not isinstance(prediction, str):
        prediction = str(prediction)
    if not isinstance(reference, str):
        reference = str(reference)
    if not isinstance(question, str):
        question = str(question)

    grade = _cot_qa_chain.invoke(
        {"question": question, "prediction": prediction, "reference": reference}
    )

    return {
        "key": "cot_qa",
        "score": grade.score,
        "comment": grade.reasoning,
    }


def run_evaluation(dataset_name: str = DATASET_NAME) -> None:
    """Kick off the LangSmith evaluation on the specified dataset."""
    client = Client()
    evaluate(
        predict_agent_answer,
        data=dataset_name,
        evaluators=[cot_qa_evaluator],
        client=client,
        experiment_prefix="finto-cot-qa",
        metadata={"model": DEFAULT_MODEL.value},
    )


if __name__ == "__main__":
    run_evaluation()
