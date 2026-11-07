# Feature Specification: ProjectOps Agent

**Feature Branch**: `001-projectops-agent`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Build a conversational AI assistant called ProjectOps Agent for managing and querying information about software projects."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer project questions from the appropriate information source (Priority: P1)

A user asks project-management questions about the Atlas domain and expects the assistant to retrieve the right information without manual routing. The system should decide whether a question is best answered from project documentation, the Knowledge Graph, or both, then present a concise answer grounded in the relevant sources.

**Why this priority**: This is the core value of the system: users need trustworthy answers about projects, ownership, work items, technologies, and operational documentation.

**Independent Test**: A user can ask a factual Atlas question, and the assistant returns the correct result based on the selected retrieval path without requiring UI or app-level intent logic.

**Acceptance Scenarios**:

1. **Given** the Atlas project documentation contains deployment guidance, **When** a user asks "What are the deployment requirements for the Atlas project?", **Then** the system retrieves the relevant documentation via RAG and responds with the deployment requirements.
2. **Given** the knowledge graph contains project and work-item relationships, **When** a user asks "Who is assigned to PBI-102?", **Then** the system queries the graph and returns the assigned person.
3. **Given** the system can access both the project corpus and the graph, **When** a user asks "Who owns the Atlas API migration and what does the migration documentation say about it?", **Then** the system combines the graph result with the document result and provides a unified answer that references both sources.

---

### User Story 2 - Execute project actions through MCP tools (Priority: P1)

A user asks the system to change project state, such as assigning a work item, changing status, or creating a new work item. The assistant must choose the correct MCP action tool and invoke it rather than modifying application state directly.

**Why this priority**: State-changing requests are critical business operations and must be handled safely, consistently, and through the approved integration channel.

**Independent Test**: A user asks for a project action and the system performs it only through an MCP tool with the correct argument schema.

**Acceptance Scenarios**:

1. **Given** a user asks "Assign PBI-102 to Alice.", **When** the assistant processes the request, **Then** it selects the appropriate MCP tool, provides the required parameters, and performs the assignment through the MCP Server.
2. **Given** a user asks "Change PBI-102 to In Progress.", **When** the agent handles the request, **Then** it uses the corresponding MCP status update tool rather than writing directly to storage or application logic.
3. **Given** a user asks "Create a new PBI for upgrading Angular.", **When** the action is requested, **Then** the system invokes an MCP tool designed to create a work item and does not bypass the server.

---

### User Story 3 - Add new tools without modifying routing logic (Priority: P2)

A developer adds a new MCP tool to the environment and expects the central agent to discover and use it without code changes to intent classification or routing logic.

**Why this priority**: This ensures the system remains extensible and does not hard-code behavior for each action or capability.

**Independent Test**: A new tool is exposed to the agent with a schema and description, and it can be selected by the agent without changing the routing implementation.

**Acceptance Scenarios**:
1. **Given** the MCP Server initially exposes tools for assigning work items, updating their status, and creating work items, **When** a developer adds a new tool such as `add_work_item_comment` and exposes its schema through MCP, **Then** the agent can discover and invoke that tool without modifications to its routing or decision-making logic.
2. **Given** the UI remains passive, **When** a new tool becomes available, **Then** the agent discovers it dynamically and invokes it as needed without any frontend logic updates.

---

### User Story 4 - Preserve architectural boundaries between UI, informational pipeline, and actions (Priority: P2)

The user interacts with a simple passive interface while the agent decides which retrieval or action capabilities are needed. The system must prevent direct database writes, action execution from the UI, and improper use of action tools as information sources.

**Why this priority**: Architectural separation prevents unsafe execution paths and ensures the agent remains the single decision-maker for request routing and capability selection.

**Independent Test**: The UI accepts input and displays output, but does not classify intent, make routing decisions, or execute state-changing operations.

**Acceptance Scenarios**:

1. **Given** a user opens the application, **When** they enter a request, **Then** the UI only sends input to the agent and displays the result; it does not inspect the message for action words or decide whether to use RAG or an MCP tool.
2. **Given** the system includes both RAG and Knowledge Graph capabilities, **When** the agent handles a request, **Then** it can use either informational source independently or in combination, but it cannot directly execute actions from those sources.
3. **Given** the action path and the informational path are separate, **When** a state-changing request is received, **Then** the system requires an MCP tool and rejects any direct modification attempt.

---

### Edge Cases

- What happens when a request requires both structured and unstructured project information? The system must combine results from the Knowledge Graph and RAG in a single reasoning flow.
- How does the system handle a request that attempts to modify project state without using MCP? The action must be rejected or blocked before any direct state change can occur.
- What happens when a new MCP tool is added? The assistant must discover it through tool metadata and select it without any hard-coded routing change.
- What happens when the user asks a question that is not clearly informational or action-oriented? The agent must determine the appropriate capability based on context and available tools rather than keyword matching.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept conversational user input through a passive UI that only sends requests to the agent and displays responses.
- **FR-002**: The system MUST use a centralized LLM-powered agent as the primary decision-maker for user requests.
- **FR-003**: The system MUST determine which capabilities are required for each request without keyword matching or hard-coded routing logic based on words such as "assign", "create", or "update".
- **FR-004**: The system MUST support informational requests through a centralized agent/graph pipeline that can retrieve project information from both RAG and a Knowledge Graph.
- **FR-005**: The RAG pipeline MUST retrieve information from a project document corpus containing project overview, architecture, team, deployment, and requirements documentation.
- **FR-006**: The Knowledge Graph MUST model the Atlas domain with at least the entities Project, Person, Work Item, and Technology and the relationships between them, including ownership, assignment, project usage, and dependency links.
- **FR-007**: The system MUST be able to answer informational questions using the RAG source alone, the Knowledge Graph source alone, or both sources together when needed.
- **FR-008**: The system MUST answer representative Atlas questions such as deployment requirements, assignee lookups, technology inventories, and ownership plus documentation summaries without requiring application-specific routing code.
- **FR-009**: The system MUST support state-changing action requests such as assigning a work item, changing a work item status, and creating a work item.
- **FR-010**: All state-changing operations MUST be executed exclusively via tools exposed by an MCP Server.
- **FR-011**: The MCP Server MUST define tool schemas for each action, including parameter validation and clear descriptions of behavior.
- **FR-012**: The agent MUST select the appropriate MCP action tool based on the user's request and the available tool metadata rather than on direct database calls or application-specific logic.
- **FR-013**: The informational capabilities MUST remain separate from the action capabilities, and RAG or Knowledge Graph retrieval MUST NOT directly execute state-changing operations.
- **FR-014**: The UI MUST remain passive and MUST NOT classify requests, select retrieval sources, invoke MCP actions directly, or decide whether a request is informational or action-oriented.
- **FR-015**: The system MUST support extending the MCP toolset with additional tools without modifying the routing or decision-making logic used to determine whether an action is required.
- **FR-016**: The system MUST operate within the fictional Atlas demonstration domain and include enough data to demonstrate RAG, graph retrieval, combined retrieval, and MCP actions without unnecessary business complexity.
- **FR-017**: The system MUST preserve the separation between informational and action capabilities such that the MCP Server is not used as an informational retrieval source and the informational pipeline cannot bypass the MCP Server for state changes.
- **FR-018**: The MCP Server MUST be independently executable and communicate with the central agent through the MCP protocol. It MUST NOT be implemented as part of the informational RAG and Knowledge Graph pipeline.
- **FR-019**: The agent MUST obtain the available action tools and their schemas through MCP tool discovery rather than relying on a hard-coded list of action capabilities.
- **FR-020**: After executing a state-changing operation, the MCP Server MUST return an execution result indicating whether the operation succeeded or failed. The system MUST NOT report an action as successful unless the MCP Server confirms its execution.
  
### Key Entities *(include if feature involves data)*

- **Project**: A software initiative such as Atlas that contains documentation, work items, technologies, and team relationships.
- **Person**: An individual contributor such as Alice, Bob, or David who may work on a project, own a migration, or be assigned to a work item.
- **Work Item**: A task or requirement such as PBI-101, PBI-102, or PBI-103 that belongs to a project and may have a status, assignee, and dependency relationships.
- **Technology**: A software technology used by a project, such as .NET 10, Angular, PostgreSQL, or Docker.
- **Documentation Artifact**: A project document or requirement source that contains deployment guidance, architecture details, team information, or migration notes.
- **MCP Tool**: A defined action capability exposed by the MCP Server, such as assigning a work item or updating work item status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can successfully answer at least three representative Atlas questions: one via RAG, one via the Knowledge Graph, and one requiring combined retrieval, without manual intent routing.
- **SC-002**: A user can successfully complete at least two action requests, including assignment and status change, using only MCP tools and without any direct application state modification.
- **SC-003**: A newly added MCP tool can be introduced into the available toolset without changing the agent's routing logic or intent-classification implementation.
- **SC-004**: All required acceptance scenarios in this specification pass in automated or integration tests, confirming the UI is passive, the informational and action paths are separate, and no keyword-based routing is used.
- **SC-005**: The system demonstrates correct handling of the Atlas domain with at least the core entities and relationships needed to answer the sample questions and execute the sample actions.

## Assumptions

- The Atlas domain is a small fictional demonstration dataset intended for validation and demonstration, not a production enterprise deployment.
- The agent can access both a document corpus and a graph store through a centralized orchestration flow that chooses the most appropriate capability set.
- Users interact through a simple chat or terminal interface that does not perform business logic beyond sending input and displaying output.
- Action requests are expected to be safe, explicit, and valid within the Atlas project-management domain, and the MCP Server enforces schema validation before execution.
- The implementation may use any compatible technology stack that satisfies the architectural constraints defined by the constitution, provided the separation between informational retrieval and action execution remains intact.
