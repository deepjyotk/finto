from __future__ import annotations

__all__ = ["PortfolioNode"]


def __getattr__(name: str):
    if name == "PortfolioNode":
        from src.nodes.financial_analysis_tool_node.financial_analysis_node import PortfolioNode

        return PortfolioNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
