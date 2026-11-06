# ProjectOps Agent Constitution

## Core Principles

### I. Autonomous Agent Orchestration

The system MUST use an LLM-powered agent as the central decision-maker for user requests.

The agent MUST autonomously determine which capabilities are required to satisfy a request. Application code MUST NOT use keyword matching, hard-coded intent classification, or `if/else` routing based on the semantic content of user messages.

The user interface MUST remain passive and MUST NOT determine whether a request is informational or actionable.

### II. Centralized Informational Pipeline

All informational requests MUST be processed through a centralized agent/graph pipeline.

The informational pipeline MUST be capable of retrieving and synthesizing information from both:

- unstructured documents through Retrieval-Augmented Generation (RAG);
- structured entities and relationships through a Knowledge Graph.

The agent MAY use either source independently when appropriate, but MUST be capable of combining both sources when a request requires information from both.

### III. Knowledge Graph and RAG Separation

RAG and Knowledge Graph retrieval MUST be implemented as distinct informational capabilities available to the centralized agent.

The Knowledge Graph MUST represent structured project information such as projects, people, work items, technologies, assignments, and dependencies.

Document retrieval MUST provide access to the project's unstructured documentation.

Neither retrieval mechanism may directly execute state-changing actions.

### IV. MCP-Only Action Execution

All state-changing operations MUST be executed exclusively through tools exposed by an MCP Server.

The agent MUST NOT directly modify application state or invoke state-changing application services outside the MCP interface.

The MCP Server MUST validate tool inputs and execute the corresponding action.

### V. Strict Informational/Action Separation

The MCP Server MUST remain architecturally separate from the informational RAG + Knowledge Graph pipeline.

The MCP Server MUST NOT be used as an informational retrieval source.

The RAG and Knowledge Graph components MUST NOT execute actions.

Informational requests and action requests MUST therefore remain separate at the capability level while still being selectable by the same central agent.

### VI. Extensible Tool Architecture

The system MUST support adding new MCP tools without modifying the agent's routing or decision-making logic.

Tools MUST expose clear schemas describing their names, parameters, and behavior.

The agent MUST be able to select among available capabilities based on the semantic requirements of the user's request.

Adding an MCP tool such as `update_work_item_status` MUST NOT require changes to code responsible for deciding whether or how the tool should be invoked.

### VII. Testable and Demonstrable Architecture

All critical architectural requirements MUST be verifiable through automated tests or explicit integration scenarios.

Tests MUST verify, at minimum:

- informational requests use the centralized agent;
- RAG retrieval can be invoked;
- Knowledge Graph retrieval can be invoked;
- RAG and Knowledge Graph results can be combined;
- action requests are executed through MCP;
- actions cannot bypass MCP;
- adding an MCP tool does not require routing changes;
- the user interface does not perform routing;
- keyword-based intent routing is not used.

The implementation SHOULD favor simplicity and demonstrability over unnecessary production complexity.

## Technical Constraints

The initial implementation SHALL use:

- Python as the primary programming language;
- LangGraph as the centralized agent orchestration framework;
- a vector store for RAG;
- Neo4j or an equivalent graph database for the Knowledge Graph;
- an MCP-compatible server implementation for action tools;
- an existing chat interface or terminal interface without custom frontend development.

The exact implementations of the vector store, LLM provider, and chat interface MAY be changed during planning if the architectural requirements remain satisfied.

The MCP Server MUST be independently executable from the informational pipeline.

## Development Workflow

Development SHALL follow the Spec-Driven Development workflow provided by Spec Kit:

1. Constitution
2. Specification
3. Clarification
4. Implementation planning
5. Task generation
6. Implementation
7. Verification

Implementation MUST NOT intentionally violate a constitutional principle for convenience.

Each major feature SHOULD have acceptance scenarios demonstrating compliance with the challenge requirements.

The implementation SHOULD include automated tests for the core agent, retrieval capabilities, MCP tools, and integration between components.

## Governance

This constitution defines the architectural constraints and quality standards for ProjectOps Agent.

The constitution takes precedence over implementation convenience and informal development practices.

Any proposed change that conflicts with a constitutional principle MUST be explicitly identified and resolved before implementation.

Amendments MUST document the reason for the change and its impact on existing requirements and implementation plans.

**Version**: 1.0.0 | **Ratified**: 2026-11-06 | **Last Amended**: 2026-11-06