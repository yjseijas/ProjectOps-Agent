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

- [ ] T001 Create the project directory structure required by the implementation plan in `src/agent/`, `src/retrieval/`, `src/mcp/`, `src/ui/`, `src/data/`, `src/config/`, and `tests/`
- [ ] T002 Initialize the Python 3.11 project configuration and dependency definitions for LangGraph, Pydantic, Neo4j, vector-store client, and pytest in `pyproject.toml` or `requirements.txt`
- [ ] T003 [P] Configure shared linting, formatting, and test tooling in `pyproject.toml` and `.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that must be complete before any user story can be implemented.

**Critical**: No user-story work can begin until this phase is complete.

- [ ] T004 Define the Atlas seed data, configuration defaults, and domain settings in `src/config/settings.py` and `src/data/atlas_seed.py`
- [ ] T005 [P] Implement the RAG and graph retrieval adapters and shared adapter boundaries in `src/retrieval/rag.py`, `src/retrieval/graph.py`, and `src/retrieval/adapters.py`
- [ ] T006 [P] Implement the MCP server shell, tool metadata discovery, and request validation in `src/mcp/server.py` and `src/mcp/schemas.py`
- [ ] T007 Implement the central LangGraph orchestrator shell and tool-planning graph in `src/agent/orchestrator.py` and `src/agent/graph.py`
- [ ] T008 Implement the passive UI shell that sends user input to the agent and renders output in `src/ui/interface.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Answer project questions from the appropriate information source (Priority: P1) 🎯 MVP

**Goal**: Allow the agent to answer Atlas questions using RAG, the knowledge graph, or both without manual routing.

**Independent Test**: A user can ask a deployment, ownership, or combined-retrieval Atlas question, and the agent returns the correct answer grounded in the appropriate source or sources.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add contract tests for retrieval capability behavior in `tests/contract/test_mcp_contracts.py` and `tests/contract/test_tool_contracts.py`
- [ ] T010 [P] [US1] Add integration tests for Atlas RAG, graph, and combined-query flows in `tests/integration/test_agent_routing.py`

### Implementation for User Story 1

- [ ] T011 [P] [US1] Implement the Atlas document corpus queries and retrieval logic in `src/retrieval/rag.py`
- [ ] T012 [P] [US1] Implement knowledge-graph retrieval for Project, Person, Work Item, and Technology relationships in `src/retrieval/graph.py`
- [ ] T013 [US1] Add the combined retrieval orchestration and source selection logic in `src/agent/orchestrator.py` and `src/agent/prompts/`
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

- [ ] T018 [P] [US2] Implement the JSON-schema validation contracts and dispatch rules for MCP actions in `src/mcp/schemas.py`
- [ ] T019 [P] [US2] Implement `assign_work_item` execution logic and Neo4j persistence in `src/mcp/tools.py`
- [ ] T020 [P] [US2] Implement `update_work_item_status` execution logic and status validation in `src/mcp/tools.py`
- [ ] T021 [US2] Implement `create_work_item` execution logic including default `Backlog` status behavior in `src/mcp/tools.py`
- [ ] T022 [US2] Add agent-side action selection using discovered MCP tool metadata rather than hard-coded keywords in `src/agent/orchestrator.py`
- [ ] T023 [US2] Enforce success/failure confirmation before reporting action completion in `src/agent/graph.py` and `src/agent/orchestrator.py`

**Checkpoint**: At this point, User Stories 1 and 2 should both work independently.

---

## Phase 5: User Story 3 - Add new tools without modifying routing logic (Priority: P2)

**Goal**: Demonstrate extensibility by adding MCP tools dynamically without route code changes.

**Independent Test**: A new tool is exposed with a schema and description, and the agent can discover and invoke it without changing routing logic.

### Tests for User Story 3

- [ ] T024 [P] [US3] Add integration coverage for dynamic MCP tool discovery in `tests/integration/test_agent_routing.py`

### Implementation for User Story 3

- [ ] T025 [P] [US3] Add runtime discovery of MCP tool metadata and enabled tools in `src/mcp/server.py`
- [ ] T026 [US3] Expose tool descriptions and JSON schema contracts through MCP metadata in `src/mcp/schemas.py`
- [ ] T027 [US3] Ensure the orchestrator can select newly exposed tools without code changes in `src/agent/orchestrator.py` and `src/agent/graph.py`

**Checkpoint**: User Story 3 should be independently validated by dynamic tool discovery.

---

## Phase 6: User Story 4 - Preserve architectural boundaries between UI, informational pipeline, and actions (Priority: P2)

**Goal**: Keep the UI passive and prevent any direct mutation or mixed retrieval/action execution.

**Independent Test**: The UI accepts and displays messages only; the agent is the sole decision-maker for routing and action execution, and direct writes are blocked.

### Tests for User Story 4

- [ ] T028 [P] [US4] Add UI and boundary tests covering passive input/output behavior in `tests/integration/test_agent_routing.py` and `tests/unit/test_rag_queries.py`

### Implementation for User Story 4

- [ ] T029 [P] [US4] Keep the UI passive and free of intent classification or action execution in `src/ui/interface.py`
- [ ] T030 [US4] Enforce read-only retrieval boundaries and no-direct-write rules across `src/retrieval/adapters.py`, `src/retrieval/graph.py`, and `src/retrieval/rag.py`
- [ ] T031 [US4] Add guardrails rejecting direct state mutation attempts from the UI or retrieval layer in `src/agent/orchestrator.py` and `src/mcp/server.py`

**Checkpoint**: All user stories should now be independently functional and conform to the architectural boundaries.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, validation, and demo readiness across the whole feature.

- [ ] T032 [P] Update release-facing documentation and architecture notes in `README.md` and `specs/001-projectops-agent/quickstart.md`
- [ ] T033 [P] Add or expand unit coverage for retrieval edge cases in `tests/unit/test_rag_queries.py` and `tests/unit/test_graph_queries.py`
- [ ] T034 Run the Atlas validation scenarios from `specs/001-projectops-agent/quickstart.md` and confirm all informational and action flows pass
- [ ] T035 Refine error handling, logging, and invalid-input guardrails across `src/agent/`, `src/retrieval/`, and `src/mcp/`
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

- All setup tasks marked `[P]` can run in parallel
- All foundational tasks marked `[P]` can run in parallel
- User Story 1 tests and model/retrieval tasks can proceed in parallel once the foundation is done
- User Story 2 contract and integration tests can run in parallel with tool implementation tasks
- User Story 3 and Story 4 work can be developed concurrently after the core foundation is ready

---

## Parallel Example: Story 1

```bash
# Launch the US1 retrieval tests together
Task: "Add contract tests for retrieval capability behavior in tests/contract/test_mcp_contracts.py and tests/contract/test_tool_contracts.py"
Task: "Add integration tests for Atlas RAG, graph, and combined-query flows in tests/integration/test_agent_routing.py"

# Launch the US1 retrieval implementation together
Task: "Implement the Atlas document corpus queries and retrieval logic in src/retrieval/rag.py"
Task: "Implement knowledge-graph retrieval for Project, Person, Work Item, and Technology relationships in src/retrieval/graph.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate the story independently using `tests/integration/test_agent_routing.py`
5. Expand to User Story 2 once the retrieval story passes cleanly

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
