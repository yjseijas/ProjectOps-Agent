"""Grounding, source attribution, and summarization behavior for the agent graph."""

from json import dumps, loads
from types import SimpleNamespace

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


class _RAGReader:
    def __init__(self, documents: list[RetrievedDocument]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, int]] = []

    async def search_documents(self, query: str, *, limit: int = 5) -> list[RetrievedDocument]:
        self.calls.append((query, limit))
        return self.documents[:limit]


class _KnowledgeGraphReader:
    def __init__(self, work_item: GraphRecord | None = None) -> None:
        self.work_item = work_item
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, project_id: str) -> GraphRecord | None:
        self.calls.append(("get_project", project_id))
        return None

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        self.calls.append(("get_work_item", work_item_id))
        if self.work_item is not None and self.work_item["entity_id"] == work_item_id:
            return self.work_item
        return None

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        self.calls.append(("list_project_technologies", project_id))
        return []


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


def _agent(
    rag: _RAGReader,
    graph: _KnowledgeGraphReader,
    llm: _FakeLLM,
) -> AgentOrchestrator:
    return AgentOrchestrator.from_readers(rag, graph, llm_client=llm)


def _final_turn(llm: _FakeLLM) -> tuple[list[dict[str, object]], dict[str, object]]:
    messages = llm.requests[1]["messages"]
    system_message = next(message for message in messages if message["role"] == "system")
    tool_messages = [message for message in messages if message["role"] == "tool"]
    return tool_messages, system_message


def test_rag_only_response_receives_grounded_document_evidence() -> None:
    request = "What does the Atlas deployment guide require?"
    document: RetrievedDocument = {
        "id": "atlas-deployment",
        "title": "Atlas Deployment Guide",
        "content": "The local demo requires Python 3.11 or newer and Neo4j.",
        "source": "atlas-deployment",
    }
    rag = _RAGReader([document])
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(None, _tool_call("search_documents", {"query": request}, "rag-call")),
        _response(
            "The local demo requires Python 3.11 or newer and Neo4j. "
            "Source: Atlas Deployment Guide."
        ),
    )

    result = _agent(rag, graph, llm).invoke(request)

    tool_messages, system_message = _final_turn(llm)
    evidence = loads(tool_messages[0]["content"])
    assert (
        result
        == "The local demo requires Python 3.11 or newer and Neo4j. Source: Atlas Deployment Guide."
    )
    assert rag.calls == [(request, 5)]
    assert graph.calls == []
    assert evidence == [document]
    assert evidence[0]["title"] == document["title"]
    assert evidence[0]["source"] == document["source"]
    assert "retrieved evidence" in system_message["content"].lower()
    assert "source" in system_message["content"].lower()
    assert "Do not expose raw JSON" in system_message["content"]


def test_knowledge_graph_only_response_receives_entity_evidence() -> None:
    request = "Who is assigned to PBI-102?"
    work_item: GraphRecord = {
        "entity_type": "WorkItem",
        "entity_id": "PBI-102",
        "properties": {"title": "Upgrade Angular application"},
        "relationships": {"ASSIGNED_TO": ("bob",)},
    }
    rag = _RAGReader([])
    graph = _KnowledgeGraphReader(work_item)
    llm = _FakeLLM(
        _response(None, _tool_call("get_work_item", {"work_item_id": "PBI-102"}, "graph-call")),
        _response("PBI-102 is assigned to Bob. Source: Knowledge Graph — WorkItem PBI-102."),
    )

    result = _agent(rag, graph, llm).invoke(request)

    tool_messages, system_message = _final_turn(llm)
    evidence = loads(tool_messages[0]["content"])
    assert result == "PBI-102 is assigned to Bob. Source: Knowledge Graph — WorkItem PBI-102."
    assert rag.calls == []
    assert graph.calls == [("get_work_item", "PBI-102")]
    assert evidence["entity_type"] == "WorkItem"
    assert evidence["entity_id"] == "PBI-102"
    assert evidence["properties"] == work_item["properties"]
    assert evidence["relationships"] == {"ASSIGNED_TO": ["bob"]}
    assert "Knowledge Graph" in system_message["content"]
    assert "entity_type" in system_message["content"]
    assert "entity_id" in system_message["content"]


def test_combined_response_receives_and_attributes_both_sources() -> None:
    request = "Who owns the Atlas migration and what do the notes say?"
    document: RetrievedDocument = {
        "id": "atlas-migration",
        "title": "Atlas API Migration Notes",
        "content": "Preserve compatibility for existing clients.",
        "source": "atlas-migration",
    }
    work_item: GraphRecord = {
        "entity_type": "WorkItem",
        "entity_id": "PBI-101",
        "properties": {"title": "Plan Atlas API migration"},
        "relationships": {"OWNS": ("alice",)},
    }
    rag = _RAGReader([document])
    graph = _KnowledgeGraphReader(work_item)
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("get_work_item", {"work_item_id": "PBI-101"}, "graph-call"),
            _tool_call("search_documents", {"query": "Atlas API migration"}, "rag-call"),
        ),
        _response(
            "Alice owns PBI-101 (Knowledge Graph - WorkItem PBI-101). "
            "The migration notes call for preserving compatibility for existing clients "
            "(Atlas API Migration Notes)."
        ),
    )

    result = _agent(rag, graph, llm).invoke(request)

    tool_messages, system_message = _final_turn(llm)
    evidence_by_call = {
        message["tool_call_id"]: loads(message["content"]) for message in tool_messages
    }
    assert "Alice owns PBI-101" in result
    assert "preserving compatibility for existing clients" in result
    assert "Knowledge Graph - WorkItem PBI-101" in result
    assert "Atlas API Migration Notes" in result
    assert evidence_by_call == {
        "graph-call": loads(dumps(work_item)),
        "rag-call": [document],
    }
    assert "attribute" in system_message["content"].lower()


def test_insufficient_evidence_instructions_and_response_acknowledge_limit() -> None:
    request = "What is the budget for the Atlas project?"
    rag = _RAGReader(
        [
            {
                "id": "atlas-overview",
                "title": "Atlas Project Overview",
                "content": "Atlas is a fictional software project.",
                "source": "atlas-overview",
            }
        ]
    )
    graph = _KnowledgeGraphReader()
    llm = _FakeLLM(
        _response(
            None,
            _tool_call("search_documents", {"query": request}, "rag-call"),
        ),
        _response(
            "The retrieved information does not specify the Atlas project budget. "
            "Source reviewed: Atlas Project Overview."
        ),
    )

    result = _agent(rag, graph, llm).invoke(request)

    tool_messages, system_message = _final_turn(llm)
    assert loads(tool_messages[0]["content"]) == rag.documents
    assert "insufficient" in system_message["content"].lower()
    assert "conflicts" in system_message["content"].lower()
    assert "does not specify" in result
