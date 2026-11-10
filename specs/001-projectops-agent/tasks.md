# Tasks: ProjectOps Agent

**Input**: Design documents from `/specs/001-projectops-agent/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Contract tests and integration tests are explicitly required by the feature specification and should be written before the implementation tasks they validate.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared tooling for the Python multi-service architecture.

- [X] T001 Create the project directory structure required by the implementation plan in `src/agent/`, `src/retrieval/`, `src/projectops_mcp/`, `src/ui/`, `src/data/`, `src/config/`, and `tests/`
- [X] T002 Initialize the Python 3.11 project configuration and dependency definitions for LangGraph, Pydantic, Neo4j, vector-store client, and pytest in `pyproject.toml` or `requirements.txt`
- [X] T003 [P] Configure shared linting, formatting, and test tooling in `pyproject.toml` and `.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that must be complete before any user story can be implemented.

**Critical**: No user-story work can begin until this phase is complete.

- [X] T004 Define the Atlas seed data, configuration defaults, and domain settings in `src/config/settings.py` and `src/data/atlas_seed.py`
- [X] T005 [P] Define the read-only retrieval interfaces and adapter boundaries for RAG and Knowledge Graph capabilities in `src/retrieval/adapters.py`
- [X] T006 [P] Create the independently executable MCP server shell in `src/projectops_mcp/server.py` and define the MCP client connection interface in `src/projectops_mcp/client.py`
- [X] T007 Define the LangGraph state and orchestration interfaces in `src/agent/orchestrator.py` and `src/agent/graph.py` without implementing semantic routing logic
- [X] T008 Implement the passive UI shell that sends user input to the agent and renders output in `src/ui/interface.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Answer project questions from the appropriate information source (Priority: P1) 🎯 MVP

**Goal**: Allow the agent to answer Atlas questions using RAG, the knowledge graph, or both without manual routing.

**Independent Test**: A user can ask a deployment, ownership, or combined-retrieval Atlas question, and the agent returns the correct answer grounded in the appropriate source or sources.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add contract tests for the RAG and Knowledge Graph retrieval interfaces in `tests/contract/test_retrieval_contracts.py`
- [ ] T010 [P] [US1] Add integration tests for Atlas RAG, graph, and combined-query flows in `tests/integration/test_agent_routing.py`

### Implementation for User Story 1

- [ ] T011 [P] [US1] Implement the Atlas document corpus queries and retrieval logic in `src/retrieval/rag.py`
- [ ] T012 [P] [US1] Implement knowledge-graph retrieval for Project, Person, Work Item, and Technology relationships in `src/retrieval/graph.py`
- [ ] T013 [US1] Configure the LangGraph agent to use LLM-based tool selection for RAG, Knowledge Graph, and combined retrieval capabilities without keyword-based or hard-coded semantic routing in `src/agent/orchestrator.py`, `src/agent/graph.py`, and `src/agent/prompts/`
- [ ] T014 [US1] Add answer grounding, source attribution, and summarization for single-source and combined retrieval responses in `src/agent/graph.py`
- [ ] T015 [US1] Validate the Atlas deployment, assignee lookup, and ownership-plus-documentation scenarios in `tests/integration/test_agent_routing.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and independently testable.

---

## Phase 4: User Story 2 - Execute project actions through MCP tools (Priority: P1)

**Goal**: Allow the agent to carry out state-changing Atlas actions only by calling MCP tools with validated schemas.

**Independent Test**: The system accepts an assignment, status-change, or creation request and performs the operation only through an MCP tool with the correct contract.

### Tests for User Story 2

- [ ] T016 [P] [US2] Add MCP contract tests for `assign_work_item`, `update_work_item_status`, and `create_work_item` in `tests/contract/test_mcp_contracts.py`
- [ ] T017 [P] [US2] Add integration tests for action execution success and failure paths in `tests/integration/test_mcp_actions.py`

### Implementation for User Story 2

- [ ] T018 [P] [US2] Implement the JSON-schema definitions and input/output validation contracts for the MCP action tools in `src/projectops_mcp/schemas.py`
- [ ] T019 [US2] Implement `assign_work_item` execution logic, input validation, and Neo4j persistence in `src/projectops_mcp/tools.py`
- [ ] T020 [US2] Implement `update_work_item_status` execution logic, status validation, and Neo4j persistence in `src/projectops_mcp/tools.py`
- [ ] T021 [US2] Implement `create_work_item` execution logic, Neo4j persistence, and default `Backlog` status behavior in `src/projectops_mcp/tools.py`
- [ ] T022 [US2] Integrate the MCP client with the LangGraph agent so MCP-exposed action tools are available to the LLM for autonomous tool selection and invocation in `src/agent/orchestrator.py` and `src/agent/graph.py`
- [ ] T023 [US2] Enforce success/failure confirmation before reporting action completion in `src/agent/graph.py` and `src/agent/orchestrator.py`

**Checkpoint**: At this point, User Stories 1 and 2 should both work independently.

---

## Phase 5: User Story 3 - Add new tools without modifying routing logic (Priority: P2)

**Goal**: Demonstrate extensibility by adding MCP tools dynamically without route code changes.

**Independent Test**: A new tool is exposed with a schema and description, and the agent can discover and invoke it without changing routing logic.

### Tests for User Story 3

- [ ] T027 [US3] Add an integration test proving that a newly added MCP tool, such as `add_work_item_comment`, can be discovered and invoked without modifying the agent's decision logic in `tests/integration/test_agent_routing.py`

### Implementation for User Story 3

- [ ] T025 [US3] Implement runtime MCP tool discovery and metadata exposure, including tool names, descriptions, and input schemas, in `src/projectops_mcp/server.py` and `src/projectops_mcp/schemas.py`
- [ ] T026 [US3] Ensure the LangGraph agent can dynamically incorporate newly discovered MCP tools into its available tool set without modifying agent decision logic in `src/agent/orchestrator.py` and `src/agent/graph.py`

**Checkpoint**: User Story 3 should be independently validated by dynamic tool discovery.

---

## Phase 6: User Story 4 - Preserve architectural boundaries between UI, informational pipeline, and actions (Priority: P2)

**Goal**: Keep the UI passive and prevent any direct mutation or mixed retrieval/action execution.

**Independent Test**: The UI accepts and displays messages only; the agent is the sole decision-maker for routing and action execution, and direct writes are blocked.

### Tests for User Story 4

- [ ] T028 [P] [US4] Add tests verifying that the UI only forwards user messages to the agent and displays responses without performing intent classification or action execution in `tests/integration/test_agent_routing.py`

### Implementation for User Story 4

- [ ] T029 [P] [US4] Keep the UI passive and free of intent classification or action execution in `src/ui/interface.py`
- [ ] T030 [US4] Enforce read-only retrieval boundaries and no-direct-write rules across `src/retrieval/adapters.py`, `src/retrieval/graph.py`, and `src/retrieval/rag.py`
- [ ] T031 [US4] Add integration tests verifying that retrieval components are read-only and that all state-changing operations are executed exclusively through MCP tools in `tests/integration/test_mcp_actions.py`

**Checkpoint**: All user stories should now be independently functional and conform to the architectural boundaries.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, validation, and demo readiness across the whole feature.

- [ ] T032 [P] Update release-facing documentation and architecture notes in `README.md` and `specs/001-projectops-agent/quickstart.md`
- [ ] T033 [P] Add or expand unit coverage for retrieval edge cases in `tests/unit/test_rag_queries.py` and `tests/unit/test_graph_queries.py`
- [ ] T034 Run the Atlas validation scenarios from `specs/001-projectops-agent/quickstart.md` and confirm all informational and action flows pass
- [ ] T035 Refine error handling, logging, and invalid-input guardrails across `src/agent/`, `src/retrieval/`, and `src/projectops_mcp/`
- [ ] T036 Final integration verification that the Atlas demo respects the UI-passive, MCP-only action, and combined-retrieval constraints across the repository

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational completion
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational; no dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational; independent from US1 for validation but shares action contracts
- **User Story 3 (P2)**: Can start after Foundational; validates dynamic discovery and extensibility
- **User Story 4 (P2)**: Can start after Foundational; validates boundary enforcement across the whole application

### Within Each User Story

- Tests must be written first and fail before implementation
- Retrieval and schema tasks precede orchestration tasks
- Action tools precede agent-side integration
- Architecture-boundary tasks ensure the final design remains compliant with the constitution

### Parallel Opportunities

- T001 and T002 can begin independently after project initialization.
- T003 can be completed alongside the initial project configuration.
- T005 and T006 can proceed in parallel because they define separate infrastructure boundaries.
- T009 and T010 can be implemented in parallel because they cover separate test files.
- T011 and T012 can proceed in parallel because they implement RAG and Knowledge Graph retrieval in separate files.
- T016 and T017 can be implemented in parallel because they cover separate test files.
- T019, T020, and T021 should be implemented sequentially because they modify the same file.
- User Stories 3 and 4 can proceed independently once their respective prerequisites are available.
- All implementation tasks must respect their associated test-first dependencies.

---

## Implementation Strategy

### Initial Development Milestone: User Story 1

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Validate RAG, Knowledge Graph, and combined retrieval independently.
5. Continue with User Story 2 to implement MCP-backed actions.

### Challenge MVP

The minimum complete challenge demonstration should include:

- User Story 1: Centralized informational pipeline with RAG and Knowledge Graph.
- User Story 2: MCP-backed action execution.
- User Story 3: Dynamic MCP tool discovery without routing changes.

User Story 4 provides additional architectural boundary verification.

### Incremental Delivery

1. Deliver retrieval capability and answer grounding for Atlas questions
2. Add MCP-backed action execution with contract validation and result confirmation
3. Add dynamic tool discovery and architectural-boundary enforcement
4. Finish with cross-cutting validation and documentation updates

---

## Summary of Task Coverage

This task list covers:

- Retrieval capability selection and combined-answering requirements from User Story 1
- MCP tool execution and validation requirements from User Story 2
- Extensible tool discovery without routing changes from User Story 3
- Passive UI and architecture-boundary enforcement from User Story 4
- Finalizing quickstart validation and repo-wide quality checks through the cross-cutting phase
