"""Contract checks for the read-only retrieval adapter interfaces.

The adapters are Protocols rather than production implementations at this
stage, so these checks exercise the contracts with explicit in-memory doubles.
"""

import inspect

import pytest

from retrieval.adapters import GraphRecord, KnowledgeGraphReader, RAGReader, RetrievedDocument


class _RAGReaderDouble:
    def __init__(self) -> None:
        self.documents = [
            {
                "id": "atlas-deployment",
                "title": "Atlas Deployment Guide",
                "content": "The local demo requires Python 3.11 or newer.",
                "source": "atlas-deployment",
            }
        ]
        self.calls: list[tuple[str, int]] = []

    async def search_documents(
        self, query: str, *, limit: int = 5
    ) -> list[RetrievedDocument]:
        self.calls.append((query, limit))
        return self.documents[:limit]


class _KnowledgeGraphReaderDouble:
    def __init__(self) -> None:
        self.project: GraphRecord = {
            "entity_type": "Project",
            "entity_id": "atlas",
            "properties": {"name": "Atlas"},
            "relationships": {"DOCUMENTED_BY": ("atlas-deployment",)},
        }
        self.work_item: GraphRecord = {
            "entity_type": "WorkItem",
            "entity_id": "PBI-102",
            "properties": {"title": "Upgrade Angular application"},
            "relationships": {"ASSIGNED_TO": ("bob",), "BELONGS_TO": ("atlas",)},
        }
        self.technologies: list[GraphRecord] = [
            {
                "entity_type": "Technology",
                "entity_id": "angular",
                "properties": {"name": "Angular"},
                "relationships": {"USED_BY": ("atlas",)},
            }
        ]
        self.calls: list[tuple[str, str]] = []

    async def get_project(self, project_id: str) -> GraphRecord | None:
        self.calls.append(("get_project", project_id))
        return self.project if project_id == self.project["entity_id"] else None

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        self.calls.append(("get_work_item", work_item_id))
        return (
            self.work_item
            if work_item_id == self.work_item["entity_id"]
            else None
        )

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        self.calls.append(("list_project_technologies", project_id))
        return self.technologies if project_id == "atlas" else []


def _assert_document_contract(document: RetrievedDocument) -> None:
    assert set(document) == {"id", "title", "content", "source"}
    assert all(isinstance(document[field], str) for field in document)


def _assert_graph_record_contract(record: GraphRecord) -> None:
    assert set(record) == {"entity_type", "entity_id", "properties", "relationships"}
    assert isinstance(record["entity_type"], str)
    assert isinstance(record["entity_id"], str)
    assert isinstance(record["properties"], dict)
    assert isinstance(record["relationships"], dict)
    assert all(isinstance(name, str) for name in record["relationships"])
    assert all(
        isinstance(ids, tuple) and all(isinstance(entity_id, str) for entity_id in ids)
        for ids in record["relationships"].values()
    )


def test_rag_reader_exposes_only_its_read_operation() -> None:
    public_methods = {
        name
        for name, value in vars(RAGReader).items()
        if not name.startswith("_") and callable(value)
    }

    assert public_methods == {"search_documents"}
    assert inspect.iscoroutinefunction(RAGReader.search_documents)

    parameters = inspect.signature(RAGReader.search_documents).parameters
    assert parameters["limit"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["limit"].default == 5


@pytest.mark.asyncio
async def test_rag_reader_returns_document_contract_without_mutating_source() -> None:
    reader: RAGReader = _RAGReaderDouble()
    original_documents = list(reader.documents)  # type: ignore[attr-defined]

    results = await reader.search_documents("Atlas deployment", limit=1)

    assert reader.calls == [("Atlas deployment", 1)]  # type: ignore[attr-defined]
    assert len(results) == 1
    _assert_document_contract(results[0])
    assert reader.documents == original_documents  # type: ignore[attr-defined]


def test_knowledge_graph_reader_exposes_only_read_operations() -> None:
    public_methods = {
        name
        for name, value in vars(KnowledgeGraphReader).items()
        if not name.startswith("_") and callable(value)
    }

    assert public_methods == {
        "get_project",
        "get_work_item",
        "list_project_technologies",
    }
    assert all(
        inspect.iscoroutinefunction(getattr(KnowledgeGraphReader, name))
        for name in public_methods
    )


@pytest.mark.asyncio
async def test_knowledge_graph_reader_returns_records_and_not_found_values() -> None:
    reader: KnowledgeGraphReader = _KnowledgeGraphReaderDouble()

    project = await reader.get_project("atlas")
    work_item = await reader.get_work_item("PBI-102")
    technologies = await reader.list_project_technologies("atlas")

    assert project is not None
    assert work_item is not None
    _assert_graph_record_contract(project)
    _assert_graph_record_contract(work_item)
    assert technologies
    for technology in technologies:
        _assert_graph_record_contract(technology)

    assert await reader.get_project("missing") is None
    assert await reader.get_work_item("missing") is None
    assert await reader.list_project_technologies("missing") == []
