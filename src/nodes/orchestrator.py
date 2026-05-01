"""Backward-compatible import path for ``OrchestratorNode``.

Prefer ``from src.nodes.orchestrator_node import OrchestratorNode`` for new code.
"""

from src.nodes.orchestrator_node import OrchestratorNode

__all__ = ["OrchestratorNode"]
