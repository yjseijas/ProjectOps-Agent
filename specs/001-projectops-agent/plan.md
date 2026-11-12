# Implementation Plan: ProjectOps Agent

**Branch**: `001-projectops-agent` | **Date**: 2026-11-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-projectops-agent/spec.md`

## Summary

ProjectOps Agent is a Python-based LangGraph application that centralizes request handling, retrieves project facts from a RAG corpus and a Neo4j Knowledge Graph, and enforces a strict separation between informational capabilities and state-changing actions. Every action request is executed through an independently runnable MCP server whose tools are discovered dynamically from MCP metadata rather than hard-coded logic. The UI remains passive and only sends input and renders output.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: LangGraph, Pydantic, MCP Python SDK, Neo4j, Qdrant, the OpenAI API for chat and `text-embedding-3-small` embeddings, plus pytest for automation.

**Storage**: Neo4j stores the Atlas domain graph; Qdrant stores Atlas documentation embeddings; a small seeded Atlas dataset provides project facts, documentation, and work items. Embedding provider and model are configured independently from the existing chat provider and model.

**Testing**: pytest, integration tests for end-to-end agent flows, contract tests for MCP tool schemas, and fixture-based validation for the Atlas demo corpus.

**Target Platform**: Local development environment and Docker-ready service composition for demos.

**Project Type**: Multi-service agent application with a central orchestration layer, retrieval adapters, and a separate MCP action server.

**Performance Goals**: Support a small Atlas demo environment with sub-second retrieval for single-source answers and a few seconds for combined RAG + graph reasoning under light usage.

**Constraints**: No keyword-based intent routing; no UI-level action execution; no direct database or application writes outside MCP; all state changes must be validated by tool schema before execution.

**Scale/Scope**: Small fictional Atlas domain; a few dozen documents, a small number of people/work items/technologies, and only the features required to prove the architecture.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passes without exception:

- Autonomous orchestration is satisfied by a single LangGraph agent that routes based on semantic request requirements and available tools.
- Centralized informational pipeline is satisfied by separate RAG and Knowledge Graph adapters available to the same agent.
- Knowledge Graph and RAG separation is preserved because retrieval is informational-only and cannot directly mutate state.
- MCP-only action execution is preserved because all assignments, status changes, and work-item creation go through an independent MCP server.
- Passive UI is preserved because the interface never classifies intent or decides whether a request is informational or action-oriented.
- Extensible tool architecture is supported through dynamic MCP tool discovery and schema-based selection.
- The architecture remains demonstrable through integration tests covering the Atlas scenarios and the constitutional constraints.

## Project Structure

### Documentation (this feature)

```text
specs/001-projectops-agent/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── agent/
│   ├── orchestrator.py
│   ├── graph.py
│   └── prompts/
├── retrieval/
│   ├── rag.py
│   ├── graph.py
│   └── adapters.py
├── projectops_mcp/
│   ├── server.py
│   ├── tools.py
│   └── schemas.py
├── ui/
│   └── interface.py
├── data/
│   └── atlas_seed.py
└── config/
    └── settings.py

tests/
├── contract/
│   └── test_mcp_contracts.py
    └── test_retrieval_contracts.py
├── integration/
│   ├── test_agent_routing.py
│   └── test_mcp_actions.py
└── unit/
    ├── test_rag_queries.py
    └── test_graph_queries.py
```

**Structure Decision**: The implementation will be organized as a small multi-service Python project with one central LangGraph agent package, separate retrieval adapters for RAG and graph access, and a dedicated MCP server package. This separation keeps informational retrieval and action execution independent while staying simple enough to validate with Atlas demo scenarios.

## Complexity Tracking

No constitution violations require justification; the design stays within the required architectural constraints and avoids unnecessary complexity.
