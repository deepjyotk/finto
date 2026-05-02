from src.nodes.screener_analysis_tool_node.screener_node import _bind_resume_values_to_form
from src.a2ui.catalog import A2UI_HITL_SURFACE_ID
from src.schemas.screener_tool_schemas.value_form import ValueForm
from src.tools.screener_tool import (
    _needs_balance_rows,
    _needs_income_rows,
    build_screener_request_from_form,
)


def test_bind_resume_values_sets_only_submitted_fields_dirty() -> None:
    form = ValueForm()

    submitted_form = _bind_resume_values_to_form(
        form,
        {
            "pe_max": "15",
            "_intent": "value",
            "unknown_field": "ignored",
        },
    )

    assert submitted_form.pe_max.value == 15.0
    assert submitted_form.pe_max.dirty is True
    assert submitted_form.pe_max.is_advanced_filter is False
    assert submitted_form.pe_max.enabled is True

    assert submitted_form.peg_max.value is None
    assert submitted_form.peg_max.dirty is False


def test_bind_resume_values_supports_a2ui_fields_and_field_meta() -> None:
    form = ValueForm()

    submitted_form = _bind_resume_values_to_form(
        form,
        {
            "fields": {
                "_intent": "value",
                "pe_max": "15",
                "pb_max": "3",
                "roe_pct_min": "8",
            },
            "fieldMeta": {
                "pe_max": {"dirty": True},
                "pb_max": {"dirty": False},
                "roe_pct_min": {"dirty": True},
            },
        },
    )

    assert submitted_form.pe_max.value == 15.0
    assert submitted_form.pe_max.dirty is True
    assert submitted_form.pb_max.value is None
    assert submitted_form.pb_max.dirty is False
    assert submitted_form.roe_pct_min.value == 8.0
    assert submitted_form.roe_pct_min.dirty is True


def test_bind_resume_values_supports_a2ui_surface_payload() -> None:
    submitted_form = _bind_resume_values_to_form(
        ValueForm(),
        {
            "surfaces": {
                A2UI_HITL_SURFACE_ID: {
                    "fields": {
                        "pe_max": "14",
                        "peg_max": "1",
                    },
                    "fieldMeta": {
                        "pe_max": {"dirty": True},
                        "peg_max": {"dirty": False},
                    },
                },
            },
        },
    )

    assert submitted_form.pe_max.value == 14.0
    assert submitted_form.pe_max.dirty is True
    assert submitted_form.peg_max.value is None
    assert submitted_form.peg_max.dirty is False


def test_bind_resume_values_normalizes_empty_strings_to_none() -> None:
    submitted_form = _bind_resume_values_to_form(ValueForm(), {"pe_max": "   "})

    assert submitted_form.pe_max.value is None
    assert submitted_form.pe_max.dirty is True


def test_build_screener_request_from_form_maps_and_skips_category_fields() -> None:
    submitted_form = _bind_resume_values_to_form(
        ValueForm(),
        {
            "pe_max": "15",
            "pb_min": "2",
            "roe_pct_min": "8",
        },
    )

    request = build_screener_request_from_form(submitted_form)

    assert request.criteria.pe_max == 15.0
    assert request.criteria.pb_max is None
    assert request.criteria.roe_min_pct == 8.0


def test_statement_row_loading_depends_on_active_criteria() -> None:
    valuation_request = build_screener_request_from_form(
        _bind_resume_values_to_form(ValueForm(), {"pe_max": "15"})
    )
    roic_request = build_screener_request_from_form(
        _bind_resume_values_to_form(ValueForm(), {"roic_pct_min": "8"})
    )

    assert _needs_income_rows(valuation_request.criteria) is False
    assert _needs_balance_rows(valuation_request.criteria) is False
    assert _needs_income_rows(roic_request.criteria) is True
    assert _needs_balance_rows(roic_request.criteria) is True
