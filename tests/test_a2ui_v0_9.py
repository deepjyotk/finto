import json

from src.a2ui.v0_9 import normalize_a2ui_messages, parse_llm_surface_document
from src.nodes.final_response_generation import FinalResponseGenerationNode


def test_normalize_data_table_rows_object_to_array() -> None:
    messages = [
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "main",
                "components": [
                    {
                        "id": "table1",
                        "component": "DataTable",
                        "columns": [{"key": "company", "label": "Company"}],
                        "rows": {
                            "EICHERMOT": {"company": "Eicher Motors Limited - EICHERMOT"},
                            "DATAPATTNS": {"company": "Data Patterns (India) Limited - DATAPATTNS"},
                        },
                    }
                ],
            },
        }
    ]

    normalized = normalize_a2ui_messages(messages)
    table = normalized[0]["updateComponents"]["components"][0]

    assert table["rows"] == [
        {"company": "Eicher Motors Limited - EICHERMOT"},
        {"company": "Data Patterns (India) Limited - DATAPATTNS"},
    ]


def test_normalize_data_table_keeps_dynamic_rows_binding() -> None:
    messages = [
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "main",
                "components": [
                    {
                        "id": "table1",
                        "component": "DataTable",
                        "columns": [{"key": "company", "label": "Company"}],
                        "rows": {"path": "/rows"},
                    }
                ],
            },
        }
    ]

    normalized = normalize_a2ui_messages(messages)
    table = normalized[0]["updateComponents"]["components"][0]

    assert table["rows"] == {"path": "/rows"}


def test_parse_llm_surface_document_normalizes_data_table_rows() -> None:
    raw = json.dumps(
        {
            "messages": [
                {
                    "version": "v0.9",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "https://explainly.ai/catalogs/finance-chat-v1.json",
                        "sendDataModel": False,
                    },
                },
                {
                    "version": "v0.9",
                    "updateComponents": {
                        "surfaceId": "main",
                        "components": [
                            {
                                "id": "root",
                                "component": "Column",
                                "children": ["table1"],
                            },
                            {
                                "id": "table1",
                                "component": "DataTable",
                                "columns": [{"key": "company", "label": "Company"}],
                                "rows": {
                                    "EICHERMOT": {
                                        "company": "Eicher Motors Limited - EICHERMOT"
                                    }
                                },
                            },
                        ],
                    },
                },
            ]
        }
    )

    messages, persisted_content = parse_llm_surface_document(raw)
    table = messages[1]["updateComponents"]["components"][1]
    persisted = json.loads(persisted_content)
    persisted_table = persisted["messages"][1]["updateComponents"]["components"][1]

    assert table["rows"] == [{"company": "Eicher Motors Limited - EICHERMOT"}]
    assert persisted_table["rows"] == [{"company": "Eicher Motors Limited - EICHERMOT"}]


def test_parse_llm_surface_document_rejects_truncated_commented_json() -> None:
    raw = """
    {
      "messages": [
        {
          "version": "v0.9",
          "updateDataModel": {
            "surfaceId": "main",
            "path": "/",
            "value": {
              "insider_transactions": [
                {"Insider": "MUSK ELON REEVE"}
                // ... (truncated for brevity, more rows available in source)
              ]
            }
          }
        }
      ]
    }
    """
    messages, persisted = parse_llm_surface_document(raw)
    assert messages == []
    assert persisted == raw
    assert FinalResponseGenerationNode._validated_a2ui_json(raw) is None


def test_validated_a2ui_json_returns_canonical_messages_object() -> None:
    raw = json.dumps(
        {
            "messages": [
                {
                    "version": "v0.9",
                    "createSurface": {
                        "surfaceId": "main",
                        "catalogId": "https://explainly.ai/catalogs/finance-chat-v1.json",
                        "sendDataModel": False,
                    },
                },
                {
                    "version": "v0.9",
                    "updateComponents": {
                        "surfaceId": "main",
                        "components": [
                            {"id": "root", "component": "Column", "children": ["t1"]},
                            {"id": "t1", "component": "Text", "text": "ok"},
                        ],
                    },
                },
            ]
        }
    )
    validated = FinalResponseGenerationNode._validated_a2ui_json(raw)
    assert validated is not None
    parsed = json.loads(validated)
    assert isinstance(parsed.get("messages"), list)
    assert parsed["messages"][0]["version"] == "v0.9"
