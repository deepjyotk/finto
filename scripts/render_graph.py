"""Utility script to render the LangGraph topology to an image and a mermaid file."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

from src.core.enums import LLMModel
from src.core.settings import llm_settings
from src.graph import Graph

DEFAULT_MODEL = LLMModel.GPT4oMini
DEFAULT_FORMAT = "png"
DEFAULT_OUTPUT = Path("wiki/artifacts/langgraph.png")
MERMAID_FILENAME = "langgraph-mermaid.mermaid"


def _draw_png(graph, output: Path) -> None:
    """Render graph as PNG using grandalf-based draw_mermaid_png."""
    png_bytes = graph.get_graph().draw_mermaid_png()
    output.write_bytes(png_bytes)


# We no longer pass output path into draw_mermaid; instead we capture the string
def _draw_mermaid_to_file(graph, output: Path) -> None:
    mermaid_str = graph.get_graph().draw_mermaid()
    output.write_text(mermaid_str, encoding="utf-8")


DRAWERS: dict[str, Callable[[Any, Path], None]] = {
    "png": _draw_png,
    # Note: draw_mermaid_png is the only image format supported with grandalf; SVG removed
    "mermaid": _draw_mermaid_to_file,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render LangGraph topology.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL.model_name,
        choices=[model.model_name for model in LLMModel],
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

    # Note: Graph.get_graph() doesn't take model parameter - models are passed via context
    compiled_graph = Graph.get_graph()

    # render the main requested format
    drawer = DRAWERS[args.format]
    drawer(compiled_graph, output_path)
    print(f"LangGraph rendered to {output_path.resolve()}")

    # always also write a mermaid file
    mermaid_path = output_path.parent / MERMAID_FILENAME
    _draw_mermaid_to_file(compiled_graph, mermaid_path)
    print(f"Mermaid topology written to {mermaid_path.resolve()}")


if __name__ == "__main__":
    main()
