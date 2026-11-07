# MCP Tool Contracts

## Tool discovery contract

The central agent must discover tool metadata from the MCP server at runtime. Tool metadata must include at least:

- tool name
- description
- parameter schema
- required inputs
- success/failure response shape

This discovery is the mechanism used to route action requests without code changes when new tools are added.

## assign_work_item

### Request schema

```json
{
  "type": "object",
  "properties": {
    "project": { "type": "string" },
    "work_item_id": { "type": "string" },
    "assignee": { "type": "string" }
  },
  "required": ["project", "work_item_id", "assignee"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "status": "success | failure",
  "work_item_id": "string",
  "assignee": "string",
  "message": "string"
}
```

## update_work_item_status

### Request schema

```json
{
  "type": "object",
  "properties": {
    "project": { "type": "string" },
    "work_item_id": { "type": "string" },
    "status": { "type": "string", "enum": ["Backlog", "In Progress", "Done", "Blocked"] }
  },
  "required": ["project", "work_item_id", "status"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "status": "success | failure",
  "work_item_id": "string",
  "new_status": "string",
  "message": "string"
}
```

## create_work_item

### Request schema

```json
{
  "type": "object",
  "properties": {
    "project": { "type": "string" },
    "title": { "type": "string" },
    "description": { "type": "string" },
    "status": { "type": "string", "enum": ["Backlog", "In Progress", "Done", "Blocked"] }
  },
  "required": ["project", "title", "description"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "status": "success | failure",
  "work_item_id": "string",
  "title": "string",
  "message": "string"
}
```

## Enforcement rules

- The MCP server must validate each action before execution.
- The agent must not report success unless the response status is success.
- The informational pipeline must never call these endpoints for retrieval.
- Additional tools may be added to the server without requiring a change to the central agent's routing code.
