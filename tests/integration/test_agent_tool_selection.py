"""LLM tool-selection behavior for the informational LangGraph."""

import asyncio
from json import dumps, loads
from types import SimpleNamespace

import pytest

from agent.orchestrator import AgentOrchestrator
from retrieval.adapters import GraphRecord, RetrievedDocument


class _FakeLLM:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []
        self.event_loops: list[asyncio.AbstractEventLoop] = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **request: object) -> object:
        self.event_loops.append(asyncio.get_running_loop())
        self.requests.append(request)
        return self.responses.pop(0)


class _RAGReader:
    def __init__(self) -> None:
        self.documents: list[RetrievedDocument] = [
            {
                "id": "atlas-deployment",
                "title": "Atlas Deployment Guide",
                "content": "Atlas requires Python 3.11 and Neo4j.",
                "source": "atlas-deployment",
            }
        ]
        self.calls: list[tuple[str, int]] = []
        self.event_loops: list[asyncio.AbstractEventLoop] = []

    async def search_documents(self, query: str, *, limit: int = 5) -> list[RetrievedDocument]:
        self.event_loops.append(asyncio.get_running_loop())
        self.calls.append((query, limit))
        return self.documents[:limit]


class _KnowledgeGraphReader:
    def __init__(self) -> None:
        self.project: GraphRecord = {
            "entity_type": "Project",
            "entity_id": "atlas",
            "properties": {"name": "Atlas"},
            "relationships": {"USES": ("neo4j",)},
        }
        self.work_item: GraphRecord = {
            "entity_type": "WorkItem",
            "entity_id": "PBI-102",
            "properties": {"title": "Upgrade Angular application"},
            "relationships": {"ASSIGNED_TO": ("bob",)},
        }
        self.technologies: list[GraphRecord] = []
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, project_id: str) -> GraphRecord | None:
        self.calls.append(("get_project", project_id))
        return self.project if project_id == "atlas" else None

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        self.calls.append(("get_work_item", work_item_id))
        return self.work_item if work_item_id == "PBI-102" else None

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        self.calls.append(("list_project_technologies", project_id))
        return self.technologies if project_id == "atlas" else []


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


@pytest.fixture
def agent_factory():
    agents: list[AgentOrchestrator] = []

    def create_agent(
        rag: _RAGReader, graph: _KnowledgeGraphReader, llm: _FakeLLM
    ) -> AgentOrchestrator:
        agent = AgentOrchestrator.from_readers(rag, graph, llm_client=llm)
        agents.append(agent)
        return agent

    yield create_agent

    for agent in agents:
        agent.close()


def test_llm_selects_rag_and_graph_generates_final_response(agent_factory) -> None:
    request = "What are Atlas's deployment prerequisites?"
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(None, _tool_call("search_documents", {"query": request}, "rag-call")),
        _response("Atlas requires Python 3.11 and Neo4j."),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    assert result == "Atlas requires Python 3.11 and Neo4j."
    assert rag.calls == [(request, 5)]
    assert graph.calls == []
    assert llm.requests[0]["messages"][-1] == {  # type: ignore[index]
        "role": "user",
        "content": request,
    }
    assert [
        tool["function"]["name"]
        for tool in llm.requests[0]["tools"]  # type: ignore[index]
    ] == [
        "search_documents",
        "get_project",
        "get_work_item",
        "list_project_technologies",
    ]
    assert llm.requests[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "rag-call",
        "content": dumps(rag.documents),
    }


def test_llm_selects_knowledge_graph_and_graph_generates_final_response(agent_factory) -> None:
    request = "Who currently owns responsibility for PBI-102?"
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(None, _tool_call("get_work_item", {"work_item_id": "PBI-102"}, "graph-call")),
        _response("PBI-102 is assigned to Bob."),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    assert result == "PBI-102 is assigned to Bob."
    assert graph.calls == [("get_work_item", "PBI-102")]
    assert rag.calls == []
    assert "PBI-102" in llm.requests[1]["messages"][-1]["content"]  # type: ignore[index,operator]


def test_llm_can_select_rag_and_knowledge_graph_together(agent_factory) -> None:
    request = "Summarize the project facts and the related deployment guidance."
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("get_project", {"project_id": "atlas"}, "project-call"),
            _tool_call("search_documents", {"query": request}, "docs-call"),
        ),
        _response("Atlas uses Neo4j and requires Python 3.11."),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    assert result == "Atlas uses Neo4j and requires Python 3.11."
    assert graph.calls == [("get_project", "atlas")]
    assert rag.calls == [(request, 5)]
    tool_messages = [
        message
        for message in llm.requests[1]["messages"]
        if message["role"] == "tool"  # type: ignore[index]
    ]
    results_by_call_id = {
        message["tool_call_id"]: loads(message["content"])
        for message in tool_messages  # type: ignore[index]
    }
    assert results_by_call_id == {
        "project-call": loads(dumps(graph.project)),
        "docs-call": rag.documents,
    }


def test_graph_follows_llm_tool_call_not_request_wording(agent_factory) -> None:
    request = "Who is assigned to PBI-102?"
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("search_documents", {"query": "assignment policy"}, "model-choice"),
        ),
        _response("The documentation describes the assignment policy."),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    assert result == "The documentation describes the assignment policy."
    assert rag.calls == [("assignment policy", 5)]
    assert graph.calls == []


@pytest.mark.asyncio
async def test_ainvoke_uses_async_graph_inside_an_existing_event_loop(agent_factory) -> None:
    request = "Describe Atlas deployment prerequisites."
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(None, _tool_call("search_documents", {"query": request}, "rag-call")),
        _response("Atlas requires Python 3.11 and Neo4j."),
    )

    result = await agent_factory(rag, graph, llm).ainvoke(request)

    assert result == "Atlas requires Python 3.11 and Neo4j."
    assert rag.calls == [(request, 5)]
    assert graph.calls == []


def test_llm_selects_project_technology_lookup(agent_factory) -> None:
    request = "Which technologies are currently associated with Atlas?"
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    graph.technologies = [
        {
            "entity_type": "Technology",
            "entity_id": "neo4j",
            "properties": {"name": "Neo4j"},
            "relationships": {"USES": ("atlas",)},
        }
    ]
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("list_project_technologies", {"project_id": "atlas"}, "technology-call"),
        ),
        _response("Atlas uses Neo4j."),
    )

    result = agent_factory(rag, graph, llm).invoke(request)

    assert result == "Atlas uses Neo4j."
    assert graph.calls == [("list_project_technologies", "atlas")]
    assert rag.calls == []
    tool_message = llm.requests[1]["messages"][-1]  # type: ignore[index]
    assert tool_message == {
        "role": "tool",
        "tool_call_id": "technology-call",
        "content": dumps(graph.technologies),
    }


def test_repeated_sync_invocations_reuse_one_event_loop(agent_factory) -> None:
    rag = _RAGReader()
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(None, _tool_call("search_documents", {"query": "first query"}, "first-call")),
        _response("First response."),
        _response(None, _tool_call("search_documents", {"query": "second query"}, "second-call")),
        _response("Second response."),
    )
    agent = agent_factory(rag, graph, llm)

    assert agent.invoke("First request.") == "First response."
    assert agent.invoke("Second request.") == "Second response."
    assert rag.calls == [("first query", 5), ("second query", 5)]
    assert graph.calls == []
    assert len(set(llm.event_loops + rag.event_loops)) == 1
