"""Helpers for Explainly's A2UI v0.9 message documents."""

from __future__ import annotations

import json
from typing import Any

from src.a2ui.catalog import A2UI_FINANCE_CHAT_CATALOG_ID, A2UI_MAIN_SURFACE_ID


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        # Drop opening fence (optional language tag) and closing fence.
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        text = text.removesuffix("```").strip()
    return text


def _extract_json_object(raw: str) -> str:
    """Best-effort extract of the outermost JSON object from model output."""
    text = _strip_code_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def build_surface_messages(
    *,
    surface_id: str,
    components: list[dict[str, Any]],
    data_model: dict[str, Any] | None = None,
    catalog_id: str = A2UI_FINANCE_CHAT_CATALOG_ID,
    send_data_model: bool = False,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": catalog_id,
                "sendDataModel": send_data_model,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": components,
            },
        },
    ]

    if data_model is not None:
        messages.append(
            {
                "version": "v0.9",
                "updateDataModel": {
                    "surfaceId": surface_id,
                    "path": "/",
                    "value": data_model,
                },
            }
        )

    return messages


def _is_dynamic_binding(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("path"), str)
        and set(value).issubset({"path", "componentId"})
    )


def _normalize_data_table_rows(component: dict[str, Any]) -> dict[str, Any]:
    if component.get("component") != "DataTable":
        return component

    rows = component.get("rows")
    if not isinstance(rows, dict) or _is_dynamic_binding(rows):
        return component

    return {
        **component,
        "rows": list(rows.values()),
    }


def normalize_a2ui_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize tolerated LLM A2UI shapes into frontend-renderable v0.9 messages."""
    normalized_messages: list[dict[str, Any]] = []

    for message in messages:
        update_components = message.get("updateComponents")
        if not isinstance(update_components, dict):
            normalized_messages.append(message)
            continue

        components = update_components.get("components")
        if not isinstance(components, list):
            normalized_messages.append(message)
            continue

        normalized_messages.append(
            {
                **message,
                "updateComponents": {
                    **update_components,
                    "components": [
                        (
                            _normalize_data_table_rows(component)
                            if isinstance(component, dict)
                            else component
                        )
                        for component in components
                    ],
                },
            }
        )

    return normalized_messages


def serialize_stored_document(
    messages: list[dict[str, Any]],
    *,
    main_surface_id: str = A2UI_MAIN_SURFACE_ID,
) -> str:
    normalized_messages = normalize_a2ui_messages(messages)
    return json.dumps(
        {
            "type": "a2ui_v0_9_document",
            "mainSurfaceId": main_surface_id,
            "messages": normalized_messages,
        },
        ensure_ascii=False,
    )


def parse_llm_surface_document(raw: str) -> tuple[list[dict[str, Any]], str]:
    """Parse the LLM's display document and return v0.9 messages + persisted content.

    Preferred shape:
    {
      "messages": [
        {"version": "v0.9", "createSurface": {...}},
        {"version": "v0.9", "updateComponents": {...}},
        {"version": "v0.9", "updateDataModel": {...}}
      ]
    }

    Tolerated legacy shape:
    {
      "components": [{ "id": "root", "component": "Column", ... }],
      "dataModel": { ... }
    }

    When parsing fails, the original text is returned so the client can fall back
    to plain-text/markdown rendering.
    """

    try:
        parsed = json.loads(_extract_json_object(raw))
    except Exception:
        return [], raw

    if not isinstance(parsed, dict):
        return [], raw

    messages = parsed.get("messages")
    if isinstance(messages, list) and messages:
        if all(
            isinstance(message, dict) and message.get("version") == "v0.9" for message in messages
        ):
            normalized_messages = normalize_a2ui_messages(messages)
            return normalized_messages, serialize_stored_document(normalized_messages)
        return [], raw

    components = parsed.get("components")
    if not isinstance(components, list) or not components:
        return [], raw

    component_ids = {component.get("id") for component in components if isinstance(component, dict)}
    if "root" not in component_ids:
        return [], raw

    if any(not isinstance(component, dict) for component in components):
        return [], raw

    data_model = parsed.get("dataModel")
    if data_model is not None and not isinstance(data_model, dict):
        return [], raw

    messages = build_surface_messages(
        surface_id=A2UI_MAIN_SURFACE_ID,
        components=components,
        data_model=data_model or {},
    )
    normalized_messages = normalize_a2ui_messages(messages)
    return normalized_messages, serialize_stored_document(normalized_messages)
