import json
from typing import List, Dict, Any
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_experimental.tools import PythonREPLTool

from src.core.enums import LLMModel


class PortfolioComputationNode:
    """Generates and executes Python to compute metrics from portfolio_data + tool_results."""

    def _collect_tool_results(self, msgs: List[BaseMessage]) -> Dict[str, float]:
        """Extract price results from ToolMessages, ignoring missing/error statuses."""
        results: Dict[str, float] = {}
        for m in msgs:
            if m.__class__.__name__ == "ToolMessage":
                try:
                    payload = json.loads(m.content) if isinstance(m.content, str) else m.content
                    if isinstance(payload, dict):
                        status = payload.get("status")
                        sym = payload.get("symbol") or payload.get("ticker") or payload.get("Symbol")
                        price = payload.get("price") or payload.get("last") or payload.get("close")
                        if status in ("not_found", "error"):
                            continue
                        if sym and price is not None:
                            try:
                                results[str(sym)] = float(price)
                            except Exception:
                                continue
                except Exception:
                    continue
        return results

    def _collect_portfolio(self, msgs: List[BaseMessage]) -> Any:
        for m in reversed(msgs):
            if getattr(m, "name", "") == "context_loader":
                try:
                    data = json.loads(m.content) if isinstance(m.content, str) else m.content
                    if isinstance(data, dict):
                        return data.get("portfolio_data", [])
                except Exception:
                    pass
                break
        return []

    def get_runnable_sequence(self, model: LLMModel):
        prompt = ChatPromptTemplate.from_template(
            "You will receive portfolio_data and tool_results (current prices).\n"
            "Write ONLY executable Python code that:\n"
            "1) Computes profit/loss per symbol: (tool_results[symbol] - buy_price) * quantity\n"
            "2) Returns a list of dicts with keys symbol (str) and profit (number), rounded to 2 decimals\n"
            "3) Skip symbols missing in tool_results (e.g., delisted).\n"
            "Variables provided:\n"
            "portfolio_data = {portfolio_json}\n"
            "tool_results = {tool_results_json}\n"
            "The code must import json and print(json.dumps(results)) at the end. No comments."
        )
        llm = ChatOpenAI(model=model.value, temperature=0)
        # Guard against accidental template variables from braces in instructions
        expected_vars = {"portfolio_json", "tool_results_json"}
        current_vars = set(getattr(prompt, "input_variables", []))
        if current_vars != expected_vars:
            safe_tmpl = (
                "Write ONLY executable Python code to compute profit/loss per symbol using provided variables. "
                "Return a list of dicts with keys symbol and profit (rounded to 2 decimals). Skip symbols missing in tool_results.\n"
                "portfolio_data = {portfolio_json}\n"
                "tool_results = {tool_results_json}\n"
                "Import json and print(json.dumps(results)) at the end. No comments."
            )
            prompt = ChatPromptTemplate.from_template(safe_tmpl)
        py = PythonREPLTool()

        def _build_inputs(msgs: List[BaseMessage]):
            return {
                "portfolio_json": json.dumps(self._collect_portfolio(msgs)),
                "tool_results_json": json.dumps(self._collect_tool_results(msgs)),
            }

        def _to_code(msg):
            return msg.content

        def _wrap_output(out):
            try:
                data = json.loads(out) if isinstance(out, str) else out
            except Exception:
                data = out
            return [AIMessage(content=json.dumps({"computed_metrics": data}), name="computation")]

        return (
            RunnableLambda(_build_inputs)
            | (prompt | llm)
            | RunnableLambda(_to_code)
            | py
            | RunnableLambda(_wrap_output)
        )
