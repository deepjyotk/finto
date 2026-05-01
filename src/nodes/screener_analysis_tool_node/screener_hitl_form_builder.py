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

_FIELD_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Valuation",
        "Price and multiple filters",
        (
            "pe_min",
            "pe_max",
            "peg_min",
            "peg_max",
            "pb_max",
            "ps_max",
            "ev_ebitda_max",
        ),
    ),
    (
        "Quality",
        "Profitability and capital efficiency",
        (
            "roe_min_pct",
            "roic_min_pct",
            "operating_margin_min_pct",
        ),
    ),
    (
        "Growth",
        "Revenue and earnings growth",
        (
            "revenue_growth_yoy_min_pct",
            "eps_growth_yoy_min_pct",
        ),
    ),
    (
        "Balance",
        "Leverage and financial strength",
        (
            "debt_to_equity_max",
        ),
    ),
)


def _field_component_ids(field_name: str) -> tuple[str, str, str | None]:
    spec = _FIELD_SPECS[field_name]
    return (
        f"fld_{field_name}",
        f"grp_{field_name}",
        f"help_{field_name}" if spec["help_text"] else None,
    )


def _number_validation_regex(spec: _FieldSpec) -> str | None:
    if spec["input_type"] != "number":
        return None
    return r"^-?\d*(\.\d+)?$"


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
            "children": ["page_title", "note_box", "threshold_tabs", "submit_row"],
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
    ]

    enabled_set = set(enabled_fields)
    action_context: dict[str, Any] = {}
    for field_name in enabled_fields:
        spec = deepcopy(_FIELD_SPECS[field_name])
        field_input_id, field_group_id, help_id = _field_component_ids(field_name)
        action_context[field_name] = {"path": f"/fields/{field_name}"}

        components.append(
            {
                "id": field_group_id,
                "component": "Column",
                "children": [field_input_id] + ([help_id] if help_id else []),
            }
        )

        field_component: dict[str, Any] = {
            "id": field_input_id,
            "component": "TextField",
            "label": spec["label"],
            "value": {"path": f"/fields/{field_name}"},
            "variant": "number" if spec["input_type"] == "number" else "shortText",
        }
        validation_regexp = _number_validation_regex(spec)
        if validation_regexp:
            field_component["validationRegexp"] = validation_regexp
        components.append(field_component)

        if help_id and spec["help_text"]:
            components.append(
                {
                    "id": help_id,
                    "component": "Text",
                    "text": spec["help_text"],
                    "variant": "caption",
                }
            )

    tabs: list[dict[str, str]] = []
    for group_index, (group_title, group_caption, group_fields) in enumerate(_FIELD_GROUPS, start=1):
        visible_fields = [field for field in group_fields if field in enabled_set]
        if not visible_fields:
            continue

        card_id = f"group_card_{group_index}"
        column_id = f"group_column_{group_index}"
        title_id = f"group_title_{group_index}"
        caption_id = f"group_caption_{group_index}"
        field_ids = [_field_component_ids(field)[1] for field in visible_fields]

        tabs.append({"title": group_title, "child": card_id})
        components.extend(
            [
                {
                    "id": card_id,
                    "component": "Card",
                    "child": column_id,
                },
                {
                    "id": column_id,
                    "component": "Column",
                    "children": [title_id, caption_id, *field_ids],
                },
                {
                    "id": title_id,
                    "component": "Text",
                    "text": group_title,
                    "variant": "h3",
                },
                {
                    "id": caption_id,
                    "component": "Text",
                    "text": group_caption,
                    "variant": "caption",
                },
            ]
        )

    components.extend(
        [
            {
                "id": "threshold_tabs",
                "component": "Tabs",
                "tabs": tabs,
            },
            {
                "id": "submit_row",
                "component": "Row",
                "children": ["submit_button"],
                "justify": "end",
                "align": "center",
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
        send_data_model=True,
    )
