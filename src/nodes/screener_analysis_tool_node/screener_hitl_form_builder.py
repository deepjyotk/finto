"""Dynamic A2UI form builder for screener HITL fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict


class _FieldSpec(TypedDict):
    label: str
    input_type: str
    help_text: str
    step: str | None
    placeholder: str | None


_FIELD_SPECS: dict[str, _FieldSpec] = {
    "pe_min": {
        "label": "P/E minimum",
        "input_type": "number",
        "help_text": "Trailing or forward P/E lower bound.",
        "step": None,
        "placeholder": None,
    },
    "pe_max": {
        "label": "P/E maximum",
        "input_type": "number",
        "help_text": "Trailing or forward P/E upper bound.",
        "step": None,
        "placeholder": None,
    },
    "peg_min": {
        "label": "PEG minimum",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "peg_max": {
        "label": "PEG maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "pb_max": {
        "label": "P/B maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "ps_max": {
        "label": "P/S maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "ev_ebitda_max": {
        "label": "EV/EBITDA maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "roe_min_pct": {
        "label": "ROE minimum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "roic_min_pct": {
        "label": "ROIC minimum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "operating_margin_min_pct": {
        "label": "Operating margin min (%)",
        "input_type": "text",
        "help_text": "Leave empty to disable this filter.",
        "step": None,
        "placeholder": "optional",
    },
    "revenue_growth_yoy_min_pct": {
        "label": "Revenue YoY growth min (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "eps_growth_yoy_min_pct": {
        "label": "EPS YoY growth min (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "debt_to_equity_max": {
        "label": "Debt/equity max",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
}


def _as_default_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def build_screener_hitl_a2ui_form(
    *, defaults: dict[str, Any], enabled_fields: tuple[str, ...]
) -> dict[str, Any]:
    """Build an A2UI form payload dynamically from enabled screener fields."""
    missing = [field for field in enabled_fields if field not in _FIELD_SPECS]
    if missing:
        raise ValueError(f"Missing form field spec(s): {', '.join(missing)}")

    components: dict[str, Any] = {
        "page_title": {
            "type": "heading",
            "props": {"text": "Stock screener - medium risk / medium return", "level": 1},
        },
        "note": {
            "type": "info-box",
            "props": {
                "text": (
                    "Edit thresholds below, then submit. "
                    "The client dispatches window event a2ui-form-submit with detail: { formId, values } "
                    "for HITL resume."
                ),
                "variant": "info",
            },
        },
    }

    child_ids: list[str] = []
    for field_name in enabled_fields:
        spec = deepcopy(_FIELD_SPECS[field_name])
        component_id = f"fld_{field_name}"
        child_ids.append(component_id)

        props: dict[str, Any] = {
            "name": field_name,
            "label": spec["label"],
            "input_type": spec["input_type"],
            "help_text": spec["help_text"],
        }
        default_value = _as_default_value(defaults.get(field_name))
        if default_value is not None:
            props["default"] = default_value
        if spec["step"] is not None:
            props["step"] = spec["step"]
        if spec["placeholder"] is not None:
            props["placeholder"] = spec["placeholder"]

        components[component_id] = {"type": "form-field", "props": props}

    components["screener_form"] = {
        "type": "form",
        "props": {
            "form_id": "hitl_screener_params",
            "title": "Screening parameters",
            "submit_label": "Run screening",
            "children": child_ids,
        },
    }

    return {
        "type": "a2ui_response",
        "root": ["page_title", "note", "screener_form"],
        "components": components,
    }
