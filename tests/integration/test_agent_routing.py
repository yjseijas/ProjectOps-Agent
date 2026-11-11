"""Central-agent wiring scenarios using scripted retrieval test doubles.

These tests validate graph/orchestrator plumbing only. Capability selection is
deliberately scripted rather than inferred from request text; semantic routing
is outside the scope until its implementation task.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from agent.orchestrator import AgentOrchestrator
from retrieval.adapters import GraphRecord, KnowledgeGraphReader, RAGReader, RetrievedDocument


class _RAGReaderDouble:
    def __init__(self, documents: list[RetrievedDocument]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, int]] = []

    async def search_documents(
        self, query: str, *, limit: int = 5
    ) -> list[RetrievedDocument]:
        self.calls.append((query, limit))
        return self.documents[:limit]


class _KnowledgeGraphReaderDouble:
    def __init__(self, records: dict[str, GraphRecord]) -> None:
        self.records = records
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, project_id: str) -> GraphRecord | None:
        self.calls.append(("get_project", project_id))
        return self.records.get(project_id)

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        self.calls.append(("get_work_item", work_item_id))
        return self.records.get(work_item_id)

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        self.calls.append(("list_project_technologies", project_id))
        record = self.records.get(project_id)
        if record is None:
            return []
        return record.get("technologies", [])  # type: ignore[typeddict-item]


def _scripted_agent_node(
    retrieval_calls: tuple[Callable[[], Any], ...],
    response: str,
    seen_requests: list[str],
) -> Callable[[dict[str, Any]], dict[str, str]]:
    """Make a test-only node with a fixed capability plan independent of input."""

    def agent_node(state: dict[str, Any]) -> dict[str, str]:
        seen_requests.append(state["user_input"])
        for retrieve in retrieval_calls:
            asyncio.run(retrieve())
        return {"response": response}

    return agent_node


def test_atlas_deployment_question_uses_central_agent_and_rag_double() -> None:
    request = "What are the deployment requirements for the Atlas project?"
    rag: RAGReader = _RAGReaderDouble(
        [
            {
                "id": "atlas-deployment",
                "title": "Atlas Deployment Guide",
                "content": (
                    "The local demo requires Python 3.11 or newer, Neo4j, and a "
                    "vector store."
                ),
                "source": "atlas-deployment",
            }
        ]
    )
    seen_requests: list[str] = []
    node = _scripted_agent_node(
        (lambda: rag.search_documents(request),),
        "Atlas deployment uses Python 3.11+, Neo4j, and a vector store.",
        seen_requests,
    )

    result = AgentOrchestrator.from_node(node).invoke(request)

    assert result == "Atlas deployment uses Python 3.11+, Neo4j, and a vector store."
    assert seen_requests == [request]
    assert rag.calls == [(request, 5)]  # type: ignore[attr-defined]


def test_atlas_assignee_question_uses_central_agent_and_graph_double() -> None:
    request = "Who is assigned to PBI-102?"
    graph: KnowledgeGraphReader = _KnowledgeGraphReaderDouble(
        {
            "PBI-102": {
                "entity_type": "WorkItem",
                "entity_id": "PBI-102",
                "properties": {"title": "Upgrade Angular application"},
                "relationships": {"ASSIGNED_TO": ("bob",), "BELONGS_TO": ("atlas",)},
            }
        }
    )
    seen_requests: list[str] = []
    node = _scripted_agent_node(
        (lambda: graph.get_work_item("PBI-102"),),
        "PBI-102 is assigned to Bob.",
        seen_requests,
    )

    result = AgentOrchestrator.from_node(node).invoke(request)

    assert result == "PBI-102 is assigned to Bob."
    assert seen_requests == [request]
    assert graph.calls == [("get_work_item", "PBI-102")]  # type: ignore[attr-defined]


def test_atlas_migration_question_uses_both_readers_through_central_agent() -> None:
    request = (
        "Who owns the Atlas API migration and what does the migration "
        "documentation say about it?"
    )
    graph: KnowledgeGraphReader = _KnowledgeGraphReaderDouble(
        {
            "PBI-101": {
                "entity_type": "WorkItem",
                "entity_id": "PBI-101",
                "properties": {"title": "Plan Atlas API migration"},
                "relationships": {"BELONGS_TO": ("atlas",)},
            },
            "alice": {
                "entity_type": "Person",
                "entity_id": "alice",
                "properties": {"name": "Alice"},
                "relationships": {"OWNS": ("PBI-101",)},
            }
        }
    )
    rag: RAGReader = _RAGReaderDouble(
        [
            {
                "id": "atlas-migration",
                "title": "Atlas API Migration Notes",
                "content": (
                    "Preserve compatibility for existing clients and coordinate "
                    "service and application changes."
                ),
                "source": "atlas-migration",
            }
        ]
    )
    seen_requests: list[str] = []
    node = _scripted_agent_node(
        (
            lambda: graph.get_work_item("PBI-101"),
            lambda: rag.search_documents("Atlas API migration"),
        ),
        (
            "Alice owns the Atlas API migration. The notes call for preserving "
            "client compatibility and coordinating service and application changes."
        ),
        seen_requests,
    )

    result = AgentOrchestrator.from_node(node).invoke(request)

    assert "Alice owns" in result
    assert "preserving client compatibility" in result
    assert seen_requests == [request]
    assert graph.calls == [("get_work_item", "PBI-101")]  # type: ignore[attr-defined]
    assert graph.records["alice"]["relationships"]["OWNS"] == ("PBI-101",)  # type: ignore[attr-defined]
    assert rag.calls == [("Atlas API migration", 5)]  # type: ignore[attr-defined]
