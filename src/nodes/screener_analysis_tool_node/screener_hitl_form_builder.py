"""Dynamic A2UI v0.9 form builder for screener HITL fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

from src.a2ui.catalog import A2UI_HITL_SURFACE_ID
from src.a2ui.v0_9 import build_surface_messages


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
def build_screener_hitl_a2ui_messages(
    *, defaults: dict[str, Any], enabled_fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Build an A2UI v0.9 form surface from enabled screener fields."""
    missing = [field for field in enabled_fields if field not in _FIELD_SPECS]
    if missing:
        raise ValueError(f"Missing form field spec(s): {', '.join(missing)}")

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["page_title", "note_box", "form_card"],
        },
        {
            "id": "page_title",
            "component": "Text",
            "text": "Stock screener - medium risk / medium return",
            "variant": "h1",
        },
        {
            "id": "note_box",
            "component": "InfoBox",
            "text": "Review the screening thresholds below, then submit to continue.",
            "variant": "info",
        },
        {
            "id": "form_card",
            "component": "Card",
            "child": "form_column",
        },
    ]

    field_group_ids: list[str] = []
    action_context: dict[str, Any] = {}
    for field_name in enabled_fields:
        spec = deepcopy(_FIELD_SPECS[field_name])
        field_input_id = f"fld_{field_name}"
        field_group_id = f"grp_{field_name}"
        field_group_ids.append(field_group_id)
        action_context[field_name] = {"path": f"/fields/{field_name}"}

        components.append(
            {
                "id": field_group_id,
                "component": "Column",
                "children": [field_input_id]
                + ([f"help_{field_name}"] if spec["help_text"] else []),
            }
        )

        components.append(
            {
                "id": field_input_id,
                "component": "TextField",
                "label": spec["label"],
                "value": {"path": f"/fields/{field_name}"},
                "variant": "number" if spec["input_type"] == "number" else "shortText",
            }
        )

        if spec["help_text"]:
            components.append(
                {
                    "id": f"help_{field_name}",
                    "component": "Text",
                    "text": spec["help_text"],
                    "variant": "caption",
                }
            )

    components.extend(
        [
            {
                "id": "form_column",
                "component": "Column",
                "children": [*field_group_ids, "submit_button"],
            },
            {
                "id": "submit_button",
                "component": "Button",
                "child": "submit_button_text",
                "variant": "primary",
                "action": {
                    "event": {
                        "name": "submit_hitl_form",
                        "context": action_context,
                    }
                },
            },
            {
                "id": "submit_button_text",
                "component": "Text",
                "text": "Run screening",
                "variant": "body",
            },
        ]
    )

    field_values: dict[str, Any] = {}
    for field_name in enabled_fields:
        default_value = defaults.get(field_name)
        if default_value is None:
            field_values[field_name] = ""
        else:
            field_values[field_name] = str(default_value)

    data_model = {
        "fields": field_values,
    }

    return build_surface_messages(
        surface_id=A2UI_HITL_SURFACE_ID,
        components=components,
        data_model=data_model,
        send_data_model=False,
    )
