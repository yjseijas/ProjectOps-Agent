"""Contract checks for the documented MCP action tool schemas."""

from projectops_mcp.schemas import ACTION_TOOL_SCHEMAS

_WORK_ITEM_STATUSES = {"Backlog", "In Progress", "Done", "Blocked"}
_RESULT_STATUSES = {"success", "failure"}


def _assert_properties(schema: dict[str, object], expected_types: dict[str, str]) -> None:
    properties = schema["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == set(expected_types)
    for name, expected_type in expected_types.items():
        property_schema = properties[name]
        assert isinstance(property_schema, dict)
        assert property_schema["type"] == expected_type


def test_action_tool_schemas_contains_documented_tools() -> None:
    assert {
        "assign_work_item",
        "update_work_item_status",
        "create_work_item",
    } <= ACTION_TOOL_SCHEMAS.keys()


def test_assign_work_item_schemas_match_contract() -> None:
    tool_schema = ACTION_TOOL_SCHEMAS["assign_work_item"]
    input_schema = tool_schema["input_schema"]
    output_schema = tool_schema["output_schema"]

    _assert_properties(
        input_schema,
        {
            "project_id": "string",
            "work_item_id": "string",
            "assignee_id": "string",
        },
    )
    assert set(input_schema["required"]) == {
        "project_id",
        "work_item_id",
        "assignee_id",
    }
    assert input_schema["additionalProperties"] is False

    _assert_properties(
        output_schema,
        {
            "status": "string",
            "work_item_id": "string",
            "assignee_id": "string",
            "message": "string",
        },
    )
    assert set(output_schema["required"]) == {"status", "work_item_id", "message"}
    assert output_schema["additionalProperties"] is False
    assert set(output_schema["properties"]["status"]["enum"]) == _RESULT_STATUSES


def test_update_work_item_status_schemas_match_contract() -> None:
    tool_schema = ACTION_TOOL_SCHEMAS["update_work_item_status"]
    input_schema = tool_schema["input_schema"]
    output_schema = tool_schema["output_schema"]

    _assert_properties(
        input_schema,
        {
            "project_id": "string",
            "work_item_id": "string",
            "status": "string",
        },
    )
    assert set(input_schema["required"]) == {"project_id", "work_item_id", "status"}
    assert input_schema["additionalProperties"] is False
    assert set(input_schema["properties"]["status"]["enum"]) == _WORK_ITEM_STATUSES

    _assert_properties(
        output_schema,
        {
            "status": "string",
            "work_item_id": "string",
            "new_status": "string",
            "message": "string",
        },
    )
    assert set(output_schema["required"]) == {"status", "work_item_id", "message"}
    assert output_schema["additionalProperties"] is False
    assert set(output_schema["properties"]["status"]["enum"]) == _RESULT_STATUSES
    assert set(output_schema["properties"]["new_status"]["enum"]) == _WORK_ITEM_STATUSES


def test_create_work_item_schemas_match_contract() -> None:
    tool_schema = ACTION_TOOL_SCHEMAS["create_work_item"]
    input_schema = tool_schema["input_schema"]
    output_schema = tool_schema["output_schema"]

    _assert_properties(
        input_schema,
        {
            "project_id": "string",
            "title": "string",
            "description": "string",
            "status": "string",
        },
    )
    assert set(input_schema["required"]) == {"project_id", "title", "description"}
    assert input_schema["additionalProperties"] is False
    assert set(input_schema["properties"]["status"]["enum"]) == _WORK_ITEM_STATUSES
    assert input_schema["properties"]["status"]["default"] == "Backlog"

    _assert_properties(
        output_schema,
        {
            "status": "string",
            "work_item_id": "string",
            "title": "string",
            "message": "string",
        },
    )
    assert set(output_schema["required"]) == {"status", "message"}
    assert output_schema["additionalProperties"] is False
    assert set(output_schema["properties"]["status"]["enum"]) == _RESULT_STATUSES
