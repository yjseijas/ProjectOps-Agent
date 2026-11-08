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
    "project_id": { "type": "string" },
    "work_item_id": { "type": "string" },
    "assignee_id": { "type": "string" }
  },
  "required": ["project_id", "work_item_id", "assignee_id"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "work_item_id": {
      "type": "string"
    },
    "assignee_id": {
      "type": "string"
    },
    "message": {
      "type": "string"
    }
  },
  "required": ["status", "work_item_id", "message"],
  "additionalProperties": false
}
```

## update_work_item_status

### Request schema

```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "work_item_id": { "type": "string" },
    "status": { "type": "string", "enum": ["Backlog", "In Progress", "Done", "Blocked"] }
  },
  "required": ["project_id", "work_item_id", "status"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "work_item_id": {
      "type": "string"
    },
    "new_status": {
      "type": "string",
      "enum": ["Backlog", "In Progress", "Done", "Blocked"]
    },
    "message": {
      "type": "string"
    }
  },
  "required": ["status", "work_item_id", "message"],
  "additionalProperties": false
}
```

## create_work_item

### Request schema

```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "title": { "type": "string" },
    "description": { "type": "string" },
    "status": { "type": "string", "enum": ["Backlog", "In Progress", "Done", "Blocked"], 
    "default": "Backlog" }
  },
  "required": ["project_id", "title", "description"],
  "additionalProperties": false
}
```

### Response schema

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "work_item_id": {
      "type": "string"
    },
    "title": {
      "type": "string"
    },
    "message": {
      "type": "string"
    }
  },
  "required": ["status", "message"],
  "additionalProperties": false
}
```

## Enforcement rules

- The MCP server must validate each action before execution.
- The agent must not report success unless the response status is success.
- The informational pipeline must never call these endpoints for retrieval.
- Additional tools may be added to the server without requiring a change to the central agent's routing code.
- When create_work_item is invoked without an explicit status, the MCP Server must initialize the new work item with status Backlog.

## MCP execution behavior

Each MCP tool must return a structured result containing its execution status and relevant information.

- Successful operations must return `status: "success"`.
- Failed operations must return `status: "failure"` or an MCP tool error.
- When an output schema is supported by the MCP SDK, it must be exposed as the tool's output schema.
- The MCP Server must communicate execution failures through the MCP protocol, including the appropriate error indicator.
- The agent must inspect the MCP result before reporting that an operation was completed.
- The agent must never report an action as successful when the MCP operation fails.

MCP tools must expose their input schemas and descriptions through standard MCP tool discovery.