"""Atlas retrieval scenarios through the centralized informational graph."""

from json import dumps, loads
from types import SimpleNamespace

import pytest

from agent.orchestrator import AgentOrchestrator
from retrieval.adapters import GraphRecord, RetrievedDocument


class _FakeLLM:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **request: object) -> object:
        self.requests.append(request)
        return self.responses.pop(0)


class _RAGReaderDouble:
    def __init__(self, documents: list[RetrievedDocument]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, int]] = []

    async def search_documents(self, query: str, *, limit: int = 5) -> list[RetrievedDocument]:
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


def _response(content: str | None = None, *tool_calls: object) -> object:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=list(tool_calls) or None)
            )
        ]
    )


def _tool_call(name: str, arguments: dict[str, object], call_id: str) -> object:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=dumps(arguments)),
    )


def _tool_messages(llm: _FakeLLM) -> list[dict[str, object]]:
    messages = llm.requests[1]["messages"]
    return [message for message in messages if message["role"] == "tool"]  # type: ignore[index]


@pytest.fixture
def agent_factory():
    agents: list[AgentOrchestrator] = []

    def create_agent(
        rag: _RAGReaderDouble,
        graph: _KnowledgeGraphReaderDouble,
        llm: _FakeLLM,
    ) -> AgentOrchestrator:
        agent = AgentOrchestrator.from_readers(rag, graph, llm_client=llm)
        agents.append(agent)
        return agent

    yield create_agent

    for agent in agents:
        agent.close()


def test_atlas_deployment_question_uses_seeded_rag_evidence(agent_factory) -> None:
    request = "What are the deployment requirements for the Atlas project?"
    document: RetrievedDocument = {
        "id": "atlas-deployment",
        "title": "Atlas Deployment Guide",
        "content": (
            "The local demo requires Python 3.11 or newer, Neo4j, and a vector store. "
            "Keep provider credentials in local environment variables."
        ),
        "source": "atlas-deployment",
    }
    rag = _RAGReaderDouble([document])
    graph = _KnowledgeGraphReaderDouble({})
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("search_documents", {"query": request}, "deployment-call"),
        ),
        _response(
            "The local demo requires Python 3.11 or newer, Neo4j, and a vector store. "
            "Keep provider credentials in local environment variables. "
            "Source: Atlas Deployment Guide."
        ),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    evidence = loads(_tool_messages(llm)[0]["content"])
    assert result == (
        "The local demo requires Python 3.11 or newer, Neo4j, and a vector store. "
        "Keep provider credentials in local environment variables. "
        "Source: Atlas Deployment Guide."
    )
    assert all(
        detail in result
        for detail in (
            "Python 3.11 or newer",
            "Neo4j",
            "vector store",
            "provider credentials in local environment variables",
            "Source: Atlas Deployment Guide",
        )
    )
    assert rag.calls == [(request, 5)]
    assert graph.calls == []
    assert evidence == [document]
    assert evidence[0]["title"] == document["title"]
    assert evidence[0]["source"] == document["source"]


def test_atlas_assignee_question_uses_seeded_graph_evidence(agent_factory) -> None:
    request = "Who is assigned to PBI-102?"
    work_item: GraphRecord = {
        "entity_type": "WorkItem",
        "entity_id": "PBI-102",
        "properties": {"title": "Upgrade Angular application"},
        "relationships": {
            "ASSIGNED_TO": ("bob",),
            "BELONGS_TO": ("atlas",),
            "OWNS": ("alice",),
            "DEPENDS_ON": ("PBI-101",),
        },
    }
    rag = _RAGReaderDouble([])
    graph = _KnowledgeGraphReaderDouble({"PBI-102": work_item})
    llm = _FakeLLM(
        _response(
            None,
            _tool_call(
                "get_work_item",
                {"work_item_id": "PBI-102"},
                "assignee-call",
            ),
        ),
        _response(
            "PBI-102 is assigned to person ID bob. Source: Knowledge Graph — WorkItem PBI-102."
        ),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    evidence = loads(_tool_messages(llm)[0]["content"])
    assert result == (
        "PBI-102 is assigned to person ID bob. Source: Knowledge Graph — WorkItem PBI-102."
    )
    assert "person ID bob" in result
    assert "Source: Knowledge Graph — WorkItem PBI-102" in result
    assert graph.calls == [("get_work_item", "PBI-102")]
    assert rag.calls == []
    assert evidence == loads(dumps(work_item))
    assert evidence["relationships"]["ASSIGNED_TO"] == ["bob"]


def test_atlas_migration_question_uses_graph_and_rag_evidence(agent_factory) -> None:
    request = (
        "Who owns the Atlas API migration and what does the migration documentation say about it?"
    )
    work_item: GraphRecord = {
        "entity_type": "WorkItem",
        "entity_id": "PBI-101",
        "properties": {
            "title": "Plan Atlas API migration",
            "assignee_id": "alice",
            "owner_id": "alice",
        },
        "relationships": {
            "BELONGS_TO": ("atlas",),
            "ASSIGNED_TO": ("alice",),
            "OWNS": ("alice",),
        },
    }
    document: RetrievedDocument = {
        "id": "atlas-migration",
        "title": "Atlas API Migration Notes",
        "content": (
            "The API migration plan should preserve compatibility for existing clients "
            "and coordinate service and application changes."
        ),
        "source": "atlas-migration",
    }
    rag = _RAGReaderDouble([document])
    graph = _KnowledgeGraphReaderDouble({"PBI-101": work_item})
    llm = _FakeLLM(
        _response(
            None,
            _tool_call(
                "get_work_item",
                {"work_item_id": "PBI-101"},
                "migration-graph-call",
            ),
            _tool_call(
                "search_documents",
                {"query": "Atlas API migration"},
                "migration-rag-call",
            ),
        ),
        _response(
            "PBI-101 is owned by person ID alice. "
            "Source: Knowledge Graph — WorkItem PBI-101. "
            "The migration plan should preserve compatibility for existing clients "
            "and coordinate service and application changes. "
            "Source: Atlas API Migration Notes."
        ),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    evidence_by_call = {
        message["tool_call_id"]: loads(message["content"]) for message in _tool_messages(llm)
    }
    assert "PBI-101 is owned by person ID alice" in result
    assert "preserve compatibility for existing clients" in result
    assert "coordinate service and application changes" in result
    assert "Source: Knowledge Graph — WorkItem PBI-101" in result
    assert "Source: Atlas API Migration Notes" in result
    assert graph.calls == [("get_work_item", "PBI-101")]
    assert rag.calls == [("Atlas API migration", 5)]
    assert evidence_by_call == {
        "migration-graph-call": loads(dumps(work_item)),
        "migration-rag-call": [document],
    }
    assert evidence_by_call["migration-graph-call"]["relationships"]["OWNS"] == ["alice"]
    migration_evidence = evidence_by_call["migration-rag-call"][0]
    assert migration_evidence["title"] == document["title"]
    assert migration_evidence["source"] == document["source"]
    assert migration_evidence["content"] == document["content"]
