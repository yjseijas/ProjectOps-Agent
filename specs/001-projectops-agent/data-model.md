# Data Model

## Core entities

### Project

| Field | Type | Notes |
|---|---|---|
| id | string | Stable identifier, e.g. `atlas` |
| name | string | Display name, e.g. `Atlas` |
| description | string | Summary of the project purpose |
| technologies | list[string] | References to technologies used by the project |
| documentation_sources | list[string] | Links to documents or corpus entries |

### Person

| Field | Type | Notes |
|---|---|---|
| id | string | Stable person identifier |
| name | string | Human-readable name, e.g. `Alice` |
| role | string | Team or ownership role |
| projects | list[string] | Projects this person is associated with |

### WorkItem

| Field | Type | Notes |
|---|---|---|
| id | string | Example `PBI-102` |
| title | string | Short task title |
| project_id | string | Parent project |
| assignee_id | string | Optional person assignment |
| status | enum | `Backlog`, `In Progress`, `Done`, etc. |
| dependencies | list[string] | Other work items this item depends on |
| description | string | High-level context or requirement |

### Technology

| Field | Type | Notes |
|---|---|---|
| id | string | Stable identifier, e.g. `dotnet10` |
| name | string | Example ` .NET 10`, `Angular`, `Docker` |
| category | string | Language, framework, infra, database |
| project_ids | list[string] | Projects using it |

### DocumentationArtifact

| Field | Type | Notes |
|---|---|---|
| id | string | Document ID |
| title | string | Deployment guide, architecture overview, migration note |
| project_id | string | Parent project |
| section | string | Team, deployment, architecture, requirements |
| content | string | Source text used by RAG |
| tags | list[string] | Keywords used for retrieval |

### MCPToolDefinition

| Field | Type | Notes |
|---|---|---|
| name | string | Operation name, e.g. `assign_work_item` |
| description | string | Human-readable description of behavior |
| input_schema | object | JSON Schema or equivalent structured contract |
| enabled | boolean | Whether it is discoverable by the agent |

## Relationships

- Project owns many DocumentationArtifact records.
- Project contains many WorkItem records.
- Person may be assigned to one or more WorkItem records.
- Person may own or contribute to one or more Project records.
- WorkItem may depend on other WorkItem records.
- Project uses one or more Technology records.
- WorkItem may be associated with one or more Technology records when a task is related to an implementation area.

## Validation rules

- Project names and IDs must be unique.
- Work item IDs must be unique within a project.
- Status values must be from a controlled enum.
- Tool schema definitions must be valid JSON Schema and must not omit required input fields.
- Action requests are valid only when the target project/work item exists and the request is within the Atlas demo model.
- RAG and graph retrieval cannot directly create, update, or delete records.

## State transitions

Work items will follow a typical lifecycle:

- `Backlog` -> `In Progress` -> `Done`
- `Backlog` may also be `Blocked`
- Assignment is a separate action that updates `assignee_id` without changing the work item status

This lifecycle is intentionally simple to keep the Atlas domain demonstrable and testable.

## Evidence and source boundaries

- The graph stores factual relationships and entity records.
- The RAG corpus stores narrative documentation and project context.
- The MCP server stores no informational retrieval state; it only validates and executes state changes.
