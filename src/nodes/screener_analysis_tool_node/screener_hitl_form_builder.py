"""Dynamic A2UI v0.9 form builder for screener HITL fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, NotRequired, TypedDict

from src.a2ui.catalog import A2UI_HITL_SURFACE_ID
from src.a2ui.v0_9 import build_surface_messages
from src.schemas.screener_tool_schemas.base import BaseScreenerForm, ScreenerFormField


class _FieldSpec(TypedDict):
    label: str
    input_type: str
    help_text: str
    step: str | None
    placeholder: str | None
    options: NotRequired[list[tuple[str, str]]]


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
        ("debt_to_equity_max",),
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
            "children": ["note_box", "threshold_tabs", "submit_row"],
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
    for group_index, (group_title, group_caption, group_fields) in enumerate(
        _FIELD_GROUPS, start=1
    ):
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
    field_meta: dict[str, dict[str, Any]] = {}
    for field_name in enabled_fields:
        default_value = defaults.get(field_name)
        if default_value is None:
            field_values[field_name] = ""
        else:
            field_values[field_name] = str(default_value)
        field_meta[field_name] = {
            "dirty": True,
            "isAdvancedFilter": False,
        }

    data_model = {
        "fields": field_values,
        "fieldMeta": field_meta,
    }

    return build_surface_messages(
        surface_id=A2UI_HITL_SURFACE_ID,
        components=components,
        data_model=data_model,
        send_data_model=True,
    )


# ---------------------------------------------------------------------------
# Category form builder — drives dynamic forms from BaseScreenerForm instances
# ---------------------------------------------------------------------------

_CATEGORY_FIELD_SPECS: dict[str, _FieldSpec] = {
    # Valuation — shared 1-to-1 with _FIELD_SPECS
    "pe_min": {
        "label": "P/E minimum",
        "input_type": "number",
        "help_text": "P/E lower bound.",
        "step": None,
        "placeholder": None,
    },
    "pe_max": {
        "label": "P/E maximum",
        "input_type": "number",
        "help_text": "P/E upper bound.",
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
    "pb_min": {
        "label": "P/B minimum",
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
    "ps_min": {
        "label": "P/S minimum",
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
    # Profitability / quality
    "roe_pct_min": {
        "label": "ROE minimum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "roe_pct_max": {
        "label": "ROE maximum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "roic_pct_min": {
        "label": "ROIC minimum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "roic_pct_max": {
        "label": "ROIC maximum (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "operating_margin_pct_min": {
        "label": "Operating margin min (%)",
        "input_type": "text",
        "help_text": "Leave empty to disable.",
        "step": None,
        "placeholder": "optional",
    },
    "operating_margin_pct_max": {
        "label": "Operating margin max (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    # Growth
    "revenue_growth_pct_min": {
        "label": "Revenue growth min (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "revenue_growth_pct_max": {
        "label": "Revenue growth max (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    # Leverage / balance sheet
    "debt_to_equity_min": {
        "label": "Debt/equity minimum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    "debt_to_equity_max": {
        "label": "Debt/equity maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    "interest_coverage_min": {
        "label": "Interest coverage min (×)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "interest_coverage_max": {
        "label": "Interest coverage max (×)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "current_ratio_min": {
        "label": "Current ratio minimum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    "current_ratio_max": {
        "label": "Current ratio maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    # Dividend / income
    "dividend_yield_pct_min": {
        "label": "Dividend yield min (%)",
        "input_type": "number",
        "help_text": "0 = no floor.",
        "step": "0.1",
        "placeholder": None,
    },
    "dividend_yield_pct_max": {
        "label": "Dividend yield max (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "payout_ratio_pct_min": {
        "label": "Payout ratio min (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    "payout_ratio_pct_max": {
        "label": "Payout ratio max (%)",
        "input_type": "number",
        "help_text": "",
        "step": "0.1",
        "placeholder": None,
    },
    # Risk / volatility
    "beta_min": {
        "label": "Beta minimum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    "beta_max": {
        "label": "Beta maximum",
        "input_type": "number",
        "help_text": "",
        "step": "0.01",
        "placeholder": None,
    },
    # Market cap (non–market_cap forms; Yahoo convention)
    "market_cap_min": {
        "label": "Market cap min (USD)",
        "input_type": "number",
        "help_text": "",
        "step": "1",
        "placeholder": None,
    },
    "market_cap_max": {
        "label": "Market cap max (USD)",
        "input_type": "number",
        "help_text": "",
        "step": "1",
        "placeholder": None,
    },
    # MarketCapForm
    "market_category": {
        "label": "Market cap category",
        "input_type": "select",
        "help_text": "",
        "step": None,
        "placeholder": None,
        "options": [
            ("Large cap", "large_cap"),
            ("Medium cap", "medium_cap"),
            ("Small cap", "small_cap"),
        ],
    },
    "min_inr": {
        "label": "Market cap min (INR)",
        "input_type": "number",
        "help_text": "",
        "step": "1",
        "placeholder": None,
    },
    "max_inr": {
        "label": "Market cap max (INR)",
        "input_type": "number",
        "help_text": "",
        "step": "1",
        "placeholder": None,
    },
    # Sector / geography / style
    "sectors": {
        "label": "Sectors",
        "input_type": "text",
        "help_text": "Comma-separated sector names.",
        "step": None,
        "placeholder": "e.g. Technology, Healthcare",
    },
    "industry": {
        "label": "Industry",
        "input_type": "text",
        "help_text": "",
        "step": None,
        "placeholder": "optional",
    },
    "country": {
        "label": "Country",
        "input_type": "text",
        "help_text": "",
        "step": None,
        "placeholder": "e.g. US",
    },
    "exchange": {
        "label": "Exchange",
        "input_type": "text",
        "help_text": "",
        "step": None,
        "placeholder": "optional",
    },
    "market_region": {
        "label": "Market region",
        "input_type": "text",
        "help_text": "",
        "step": None,
        "placeholder": "e.g. domestic",
    },
    "style": {
        "label": "Investment style",
        "input_type": "text",
        "help_text": "e.g. quality, momentum, blue-chip.",
        "step": None,
        "placeholder": "optional",
    },
    "sensitivity_type": {
        "label": "Sensitivity type",
        "input_type": "text",
        "help_text": "e.g. defensive, cyclical.",
        "step": None,
        "placeholder": "optional",
    },
}

_META_FIELDS = frozenset({"category", "description"})


def _category_field_component_ids(field_name: str) -> tuple[str, str, str | None]:
    spec = _CATEGORY_FIELD_SPECS[field_name]
    return (
        f"fld_{field_name}",
        f"grp_{field_name}",
        f"help_{field_name}" if spec["help_text"] else None,
    )


def _build_field_components(
    field_name: str,
    action_context: dict[str, Any],
    components: list[dict[str, Any]],
) -> None:
    """Append TextField + optional help Text components for one form field."""
    spec = _CATEGORY_FIELD_SPECS[field_name]
    field_input_id, field_group_id, help_id = _category_field_component_ids(field_name)
    action_context[field_name] = {"path": f"/fields/{field_name}"}

    components.append(
        {
            "id": field_group_id,
            "component": "Column",
            "children": [field_input_id] + ([help_id] if help_id else []),
        }
    )

    input_type = spec["input_type"]
    if input_type == "select":
        opts = spec.get("options") or ()
        field_component = {
            "id": field_input_id,
            "component": "SelectField",
            "label": spec["label"],
            "value": {"path": f"/fields/{field_name}"},
            "options": [{"label": lbl, "value": val} for lbl, val in opts],
        }
    else:
        field_component = {
            "id": field_input_id,
            "component": "TextField",
            "label": spec["label"],
            "value": {"path": f"/fields/{field_name}"},
            "variant": "number" if input_type == "number" else "shortText",
        }
        if input_type == "number":
            field_component["validationRegexp"] = r"^-?\d*(\.\d+)?$"
        if spec.get("placeholder"):
            field_component["placeholder"] = spec["placeholder"]
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


def build_category_form_a2ui_messages(
    form: BaseScreenerForm, *, intent: str
) -> list[dict[str, Any]]:
    """Build an A2UI v0.9 form surface from a :class:`BaseScreenerForm` instance.

    Fields with ``is_advanced_filter=False`` appear in the **Key Filters** tab;
    fields with ``is_advanced_filter=True`` appear in the **Advanced** tab.
    The ``_intent`` key is injected into the data model and action context so it
    is returned transparently on resume without any frontend changes.
    """
    form_data = form.model_dump()
    basic_fields: list[str] = []
    advanced_fields: list[str] = []
    enabled_field_models: dict[str, ScreenerFormField[Any]] = {}

    for field_name, field_value in form_data.items():
        if field_name in _META_FIELDS:
            continue
        if not isinstance(field_value, dict):
            continue
        ff = ScreenerFormField.model_validate(field_value)
        if not ff.enabled:
            continue
        if field_name not in _CATEGORY_FIELD_SPECS:
            continue
        enabled_field_models[field_name] = ff
        if ff.is_advanced_filter:
            advanced_fields.append(field_name)
        else:
            basic_fields.append(field_name)

    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["note_box", "threshold_tabs", "submit_row"],
        },
        {
            "id": "note_box",
            "component": "InfoBox",
            "text": "Review the screening parameters below, then submit to continue.",
            "variant": "info",
        },
    ]

    action_context: dict[str, Any] = {}

    for field_name in basic_fields + advanced_fields:
        _build_field_components(field_name, action_context, components)

    # _intent is a hidden value, not rendered as a visible field
    action_context["_intent"] = {"path": "/fields/_intent"}

    tabs: list[dict[str, Any]] = []

    for tab_index, (tab_title, tab_caption, tab_fields) in enumerate(
        [
            ("Key Filters", "Core parameters that define this category", basic_fields),
            ("Advanced", "Additional refinement filters", advanced_fields),
        ],
        start=1,
    ):
        if not tab_fields:
            continue

        card_id = f"tab_card_{tab_index}"
        column_id = f"tab_column_{tab_index}"
        title_id = f"tab_title_{tab_index}"
        caption_id = f"tab_caption_{tab_index}"
        field_group_ids = [_category_field_component_ids(f)[1] for f in tab_fields]

        tabs.append({"title": tab_title, "child": card_id})
        components.extend(
            [
                {"id": card_id, "component": "Card", "child": column_id},
                {
                    "id": column_id,
                    "component": "Column",
                    "children": [title_id, caption_id, *field_group_ids],
                },
                {"id": title_id, "component": "Text", "text": tab_title, "variant": "h3"},
                {"id": caption_id, "component": "Text", "text": tab_caption, "variant": "caption"},
            ]
        )

    components.extend(
        [
            {"id": "threshold_tabs", "component": "Tabs", "tabs": tabs},
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
                "action": {"event": {"name": "submit_hitl_form", "context": action_context}},
            },
            {
                "id": "submit_button_text",
                "component": "Text",
                "text": "Run screening",
                "variant": "body",
            },
        ]
    )

    # Build data model: serialise each ScreenerFormField.value to string
    field_values: dict[str, Any] = {"_intent": intent}
    field_meta: dict[str, dict[str, Any]] = {}
    for field_name in basic_fields + advanced_fields:
        field_model = enabled_field_models[field_name]
        val = field_model.value
        field_values[field_name] = "" if val is None else str(val)
        field_meta[field_name] = {
            "dirty": field_model.dirty,
            "isAdvancedFilter": field_model.is_advanced_filter,
        }

    return build_surface_messages(
        surface_id=A2UI_HITL_SURFACE_ID,
        components=components,
        data_model={"fields": field_values, "fieldMeta": field_meta},
        send_data_model=True,
    )
