# Research

## Decision: Use a single LangGraph-based agent with two informational adapters and one MCP execution boundary

The system will have one central orchestrator that inspects the user's request, sees the available capabilities, and decides whether to invoke a document retrieval tool, a graph query tool, a combined retrieval flow, or an MCP action. This aligns with the requirement that the UI remain passive and that intent selection be semantic rather than keyword-based.

### Rationale

- The constitution requires the agent to be the central decision-maker.
- The Atlas use cases need both unstructured document context and structured relationships.
- State-changing operations are explicitly separated from informational retrieval, which requires an independent execution layer.
- Dynamic tool discovery is required so new MCP tools can be added without modifying routing logic.

### Alternatives considered

- Hard-coded if/else routing by words such as "assign" or "create": rejected because it violates the constitutional requirement against keyword-based intent routing.
- Embedding action logic directly inside the UI or service layer: rejected because this would violate the passive UI and action separation constraints.
- Treating the MCP server as an informational source: rejected because the constitution forbids using the MCP server for retrieval.

## Decision: Use a vector store for project documents and Neo4j for entity relationships

The informational layer will separate document retrieval from graph retrieval so the agent can answer questions with either source alone or both together.

### Rationale

- RAG is the correct fit for unstructured project documentation such as deployment guides, architecture notes, and migration write-ups.
- A graph database is the natural fit for relationships such as ownership, work-item assignment, dependencies, and technology usage.
- The Atlas requirements explicitly require both sources and their combined use.

### Alternatives considered

- Single-store document-only implementation: rejected because it would not satisfy the knowledge-graph requirements.
- Direct application queries to storage from the UI or tool layer: rejected because the architecture requires centralized orchestration and MCP-only actions.

## Decision: Expose all mutation actions through an independently runnable MCP server

State changes will be expressed as MCP tools with validated input schemas, including assign_work_item, update_work_item_status, and create_work_item.

### Rationale

- This satisfies FR-009 through FR-020 and the constitution's MCP-only action rule.
- Tool metadata can be discovered dynamically, enabling extensibility without routing changes.
- The server can return structured execution results so the agent only reports success after receiving confirmation from the MCP layer.

### Alternatives considered

- Direct service calls from the agent: rejected because the constitution prohibits direct state changes outside MCP.
- Embedding action implementations inside the retrieval layer: rejected because the informational and action paths must remain separate.

## Decision: Keep the UI passive and thin

The user interface should only accept user input, send it to the orchestration layer, and render the final answer.

### Rationale

- The constitution requires the UI to remain passive.
- The acceptance scenarios explicitly require no UI-side classification or action invocation.

### Alternatives considered

- Front-end intent detection and conditional routing: rejected because it violates the architectural requirement and would make the system harder to test.

## Research outcome

All key unknowns are resolved by the specification and constitution. No additional clarification is required before implementation planning. The planned architecture preserves the required boundaries while remaining small, demonstrable, and extensible for the Atlas demo domain.
