"""LangSmith CoT QA evaluation for the LangGraph agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
from typing import Any, Dict, Mapping
from uuid import uuid4

# Windows requires SelectorEventLoop for psycopg async — set policy before any async imports.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langsmith import Client
from langsmith.evaluation import aevaluate
from langsmith.schemas import Example, Run
from pydantic import BaseModel, Field

from src.core.enums import LLMModel
from src.dependencies import build_agent_graph
import dotenv

dotenv.load_dotenv()


# DATASET_NAME = "finto-qa-dataset-v2"
DATASET_NAME = "finto-yf-tools-getBalanceSheet"
EVALUATION_MODEL = LLMModel.GPT4oMini

# Model configuration for evaluation
ORCHESTRATOR_MODEL = LLMModel.GPT4oMini
PORTFOLIO_MODEL = LLMModel.GPT4p1
NEWS_MODEL = LLMModel.GPT4oMini



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


def _a2ui_to_text(a2ui: dict) -> str:
    """Convert an a2ui_response JSON to a plain-text string for evaluation."""
    components = a2ui.get("components", {})
    root_ids = a2ui.get("root", list(components.keys()))
    lines: list[str] = []

    for cid in root_ids:
        comp = components.get(cid)
        if not comp:
            continue
        ctype = comp.get("type", "")
        props = comp.get("props", {})

        if ctype == "heading":
            lines.append(props.get("text", ""))

        elif ctype in ("text", "paragraph", "markdown"):
            lines.append(props.get("text") or props.get("content", ""))

        elif ctype == "badge":
            lines.append(f"[{props.get('text', '')}]")

        elif ctype == "data-table":
            columns = props.get("columns", [])
            rows = props.get("rows", [])
            if columns:
                lines.append("\t".join(c.get("label", c.get("key", "")) for c in columns))
            for row in rows:
                lines.append("\t".join(str(v) for v in row))

        elif ctype == "chart":
            # Summarise chart data as a series of key: value pairs
            data = props.get("data", [])
            x_key = props.get("x_key", "name")
            data_keys = props.get("data_keys", [])
            for point in data:
                vals = ", ".join(f"{k}: {point.get(k)}" for k in data_keys if k in point)
                lines.append(f"{point.get(x_key, '')}: {vals}")

        elif ctype in ("metric", "kpi"):
            label = props.get("label") or props.get("title", "")
            value = props.get("value", "")
            lines.append(f"{label}: {value}")

    return "\n".join(line for line in lines if line)


def _extract_answer(graph_result: Any) -> str:
    """Extract the assistant's final answer from the LangGraph output.

    Handles two formats:
    - Plain text AIMessage content (normal chat)
    - a2ui_response JSON (structured UI output) — converted to readable text for evaluation
    """
    raw = ""
    if isinstance(graph_result, dict):
        # Prefer the top-level state field over digging through messages
        raw = graph_result.get("final_rendered_ui_answer") or ""
        if not raw:
            messages = graph_result.get("messages") or []
            if messages:
                raw = _message_content_to_str(messages[-1])
    elif isinstance(graph_result, list) and graph_result:
        raw = _message_content_to_str(graph_result[-1])
    else:
        raw = str(graph_result or "")

    # If the output is an a2ui_response JSON, convert it to plain text
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            parsed = json.loads(raw)
            if parsed.get("type") == "a2ui_response":
                return _a2ui_to_text(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass

    return raw


def _generate_experiment_prefix(
    dataset_name: str,
    orchestrator_model: LLMModel,
    portfolio_model: LLMModel,
    web_search_model: LLMModel,
) -> str:
    """Generate experiment prefix with dataset name and model names."""
    orchestrator_name = orchestrator_model.model_name.replace(".", "-")
    portfolio_name = portfolio_model.model_name.replace(".", "-")
    news_name = web_search_model.model_name.replace(".", "-")
    return f"{dataset_name}_orchestrator-{orchestrator_name}_portfolio-{portfolio_name}_news-{news_name}"


def predict_agent_answer(compiled_graph: Any):
    """Return a coroutine function that invokes the agent for one dataset row.

    The compiled graph is built once in `run_evaluation` and closed over here
    so the same event loop / connection pool is reused for every question.
    """

    async def _predict(
        inputs: Mapping[str, Any], config: RunnableConfig | None = None, **_: Any
    ) -> Dict[str, str]:
        question = inputs.get("input") or inputs.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Each dataset example must include a non-empty 'input' or 'question'.")

        run_config: RunnableConfig = {}
        if config:
            run_config.update(config)
        configurable = dict(run_config.get("configurable", {}))
        configurable.setdefault("thread_id", str(uuid4()))
        run_config["configurable"] = configurable

        graph_state = {"messages": [HumanMessage(content=question.strip())]}
        context = {
            "user_id": uuid4(),
            "orchestrator_model": ORCHESTRATOR_MODEL,
            "portfolio_model": PORTFOLIO_MODEL,
            "web_search_model": NEWS_MODEL,
        }
        result = await compiled_graph.ainvoke(graph_state, config=run_config, context=context)

        # Collect which tools were called during this run (for tool_routing_evaluator)
        tools_called: list[str] = []
        if isinstance(result, dict):
            for msg in result.get("messages", []):
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        if name:
                            tools_called.append(name)

        return {"answer": _extract_answer(result), "tools_called": tools_called}

    return _predict


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

_cot_qa_chain = _cot_qa_prompt | ChatOpenAI(
    model=EVALUATION_MODEL.model_name, **EVALUATION_MODEL.llm_kwargs
).with_structured_output(CotQAGrade)


def tool_routing_evaluator(run: Run, example: Example, **_: Any) -> Dict[str, Any]:
    """
    Rule-based (free) evaluator: checks whether the agent called the expected tools.

    The dataset example's output dict can include an optional 'expected_tools' list, e.g.:
        {"output": "...", "expected_tools": ["get_balance_sheet", "get_symbol_names"]}

    If 'expected_tools' is absent the evaluator is skipped (score=None).
    """
    expected_tools: list[str] | None = (example.outputs or {}).get("expected_tools")
    if not expected_tools:
        return {"key": "tool_routing", "score": None, "comment": "No expected_tools defined; skipped."}

    tools_called: list[str] = (run.outputs or {}).get("tools_called", [])
    tools_called_set = set(tools_called)

    missing = [t for t in expected_tools if t not in tools_called_set]
    if missing:
        return {
            "key": "tool_routing",
            "score": 0.0,
            "comment": f"Missing expected tools: {missing}. Called: {tools_called}",
        }

    return {
        "key": "tool_routing",
        "score": 1.0,
        "comment": f"All expected tools called. Called: {tools_called}",
    }


def cot_qa_evaluator(run: Run, example: Example, **_: Any) -> Dict[str, Any]:
    """Grade the agent answer using the CoT QA evaluator chain."""
    outputs = run.outputs or {}
    prediction = outputs.get("answer", "")
    reference = (example.outputs or {}).get("output", "") or (example.outputs or {}).get(
        "answer", ""
    )
    question = (example.inputs or {}).get("input", "") or (example.inputs or {}).get("question", "")

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


async def run_evaluation(dataset_name: str = DATASET_NAME, max_concurrency: int = 1) -> None:
    """Kick off the LangSmith evaluation on the specified dataset."""
    # Build the graph once — the async pool and Lock stay bound to this single event loop.
    print("Building agent graph...", flush=True)
    compiled_graph = await build_agent_graph().get_graph()
    print("Graph ready. Starting evaluation...", flush=True)

    client = Client()
    experiment_prefix = _generate_experiment_prefix(
        dataset_name, ORCHESTRATOR_MODEL, PORTFOLIO_MODEL, NEWS_MODEL
    )
    results = await aevaluate(
        predict_agent_answer(compiled_graph),
        data=dataset_name,
        evaluators=[tool_routing_evaluator, cot_qa_evaluator],
        client=client,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata={
            "orchestrator_model": ORCHESTRATOR_MODEL.model_name,
            "portfolio_model": PORTFOLIO_MODEL.model_name,
            "web_search_model": NEWS_MODEL.model_name,
            "evaluation_model": EVALUATION_MODEL.model_name,
        },
    )
    experiment_id = getattr(results, "experiment_name", None)
    if experiment_id:
        print(f"LangSmith experiment_id: {experiment_id}", flush=True)
    else:
        print("Evaluation finished but experiment_id was not returned.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LangSmith CoT QA evaluation")
    parser.add_argument(
        "--dataset-name",
        type=str,
        default=DATASET_NAME,
        help=f"Name of the dataset to evaluate (default: {DATASET_NAME})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Max concurrent agent invocations (default: 1).",
    )
    args = parser.parse_args()

    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            run_evaluation(dataset_name=args.dataset_name, max_concurrency=args.concurrency)
        )
    except KeyboardInterrupt:
        print("\nInterrupted — cancelling pending tasks...", flush=True)
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        print("Stopped.", flush=True)
    finally:
        loop.close()
