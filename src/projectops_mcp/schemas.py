"""JSON Schema definitions for ProjectOps MCP action tools."""

ACTION_TOOL_SCHEMAS: dict[str, dict[str, dict[str, object]]] = {
    "assign_work_item": {
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "work_item_id": {"type": "string"},
                "assignee_id": {"type": "string"},
            },
            "required": ["project_id", "work_item_id", "assignee_id"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "failure"]},
                "work_item_id": {"type": "string"},
                "assignee_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["status", "work_item_id", "message"],
            "additionalProperties": False,
        },
    },
    "update_work_item_status": {
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "work_item_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["Backlog", "In Progress", "Done", "Blocked"],
                },
            },
            "required": ["project_id", "work_item_id", "status"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "failure"]},
                "work_item_id": {"type": "string"},
                "new_status": {
                    "type": "string",
                    "enum": ["Backlog", "In Progress", "Done", "Blocked"],
                },
                "message": {"type": "string"},
            },
            "required": ["status", "work_item_id", "message"],
            "additionalProperties": False,
        },
    },
    "create_work_item": {
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["Backlog", "In Progress", "Done", "Blocked"],
                    "default": "Backlog",
                },
            },
            "required": ["project_id", "title", "description"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "failure"]},
                "work_item_id": {"type": "string"},
                "title": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["status", "message"],
            "additionalProperties": False,
        },
    },
}
