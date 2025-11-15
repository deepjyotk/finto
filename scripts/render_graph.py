"""Utility script to render the LangGraph topology to an image."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Callable

from src.core.enums import LLMModel
from src.core.settings import llm_settings
from src.graph import Graph

DEFAULT_MODEL = LLMModel.GPT4oMini
DEFAULT_FORMAT = "png"
DEFAULT_OUTPUT = Path("artifacts/langgraph.png")


def _draw_png(graph, output: Path) -> None:
    graph.draw_png(str(output))


def _draw_svg(graph, output: Path) -> None:
    graph.draw_svg(str(output))


def _draw_mermaid(graph, output: Path) -> None:
    graph.draw_mermaid(str(output))


DRAWERS: dict[str, Callable] = {
    "png": _draw_png,
    "svg": _draw_svg,
    "mermaid": _draw_mermaid,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render LangGraph topology.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL.value,
        choices=[model.value for model in LLMModel],
        help="LLM model to use when constructing the graph.",
    )
    parser.add_argument(
        "--format",
        default=DEFAULT_FORMAT,
        choices=sorted(DRAWERS.keys()),
        help="Output format for the rendered graph.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to write the rendered graph artifact.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("OPENAI_API_KEY", llm_settings.openai_api_key)

    selected_model = LLMModel(args.model)
    compiled_graph = Graph.get_graph(selected_model).get_graph()

    drawer = DRAWERS[args.format]
    drawer(compiled_graph, output_path)

    print(f"LangGraph rendered to {output_path.resolve()}")


if __name__ == "__main__":
    main()

