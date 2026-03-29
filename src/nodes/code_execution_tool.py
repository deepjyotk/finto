"""Generic Python code executor tool for LangGraph ToolNode.

This module is intentionally free of any domain knowledge.  The caller is
responsible for providing an `execution_env_factory` that builds the sandboxed
namespace in which the generated code will run.
"""

import contextlib
import io
from typing import Awaitable, Callable, Dict

from langchain_core.tools import tool


def build_execute_code_tool(
    execution_env_factory: Callable[[], Awaitable[Dict[str, object]]],
):
    """Create the ``execute_python_code`` LangChain tool.

    The tool itself knows nothing about portfolios, financial data, or any
    domain-specific details.  All of that knowledge lives in the
    ``execution_env_factory`` provided by the caller.

    Args:
        execution_env_factory: Async callable that returns a fully-populated
                               execution namespace dict for each invocation.
                               The caller (e.g. PortfolioNode) is responsible
                               for building and injecting this.
    """

    @tool
    async def execute_python_code(code: str) -> str:
        """Execute Python code and return stdout output or error details."""
        if not code:
            return "No code provided to execute."

        execution_env = await execution_env_factory()

        stdout_capture = io.StringIO()
        stdout_text = ""

        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, execution_env, execution_env)
            stdout_text = stdout_capture.getvalue().strip() or "<no output printed to stdout>"
            sections = [
                "STATUS: success",
                f"STDOUT:\n{stdout_text}",
            ]
        except Exception as exc:
            stdout_text = stdout_capture.getvalue().strip()
            sections = [
                "STATUS: error",
                *([f"STDOUT:\n{stdout_text}"] if stdout_text else []),
                f"ERROR:\n{repr(exc)}",
                "\nExamine the above error message. Modify the code to fix the error.",
            ]

        if "=== SUGGESTED NEW METHOD ===" in stdout_text:
            sections.append(
                "\n⚠️ IMPORTANT: The output contains method suggestions that should be preserved in the final response."
            )

        return "\n\n".join(sections)

    return execute_python_code
