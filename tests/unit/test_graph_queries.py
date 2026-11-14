from __future__ import annotations

import inspect

import pytest

from config.settings import Settings
from retrieval.adapters import GraphRecord
from retrieval.graph import Neo4jKnowledgeGraphReader


class _Result:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    async def single(self) -> dict[str, object] | None:
        return self._records[0] if self._records else None

    async def data(self) -> list[dict[str, object]]:
        return self._records


class _Session:
    def __init__(self, driver: _Driver, database: str) -> None:
        self._driver = driver
        self.database = database
        self.closed = False

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.closed = True

    async def run(self, query: str, **parameters: object) -> _Result:
        self._driver.queries.append((query, parameters, self.database))
        return _Result(self._driver.responses.pop(0))


class _Driver:
    def __init__(self, responses: list[list[dict[str, object]]] | None = None) -> None:
        self.responses = responses or []
        self.queries: list[tuple[str, dict[str, object], str]] = []
        self.sessions: list[_Session] = []
        self.closed = False

    def session(self, *, database: str) -> _Session:
        session = _Session(self, database)
        self.sessions.append(session)
        return session

    async def close(self) -> None:
        self.closed = True


def _reader(
    responses: list[list[dict[str, object]]] | None = None,
) -> tuple[Neo4jKnowledgeGraphReader, _Driver]:
    driver = _Driver(responses)
    reader = Neo4jKnowledgeGraphReader(
        Settings(neo4j_database="atlas-test"),
        driver=driver,  # type: ignore[arg-type]
    )
    return reader, driver


def _assert_graph_record(record: GraphRecord) -> None:
    assert set(record) == {"entity_type", "entity_id", "properties", "relationships"}
    assert isinstance(record["entity_type"], str)
    assert isinstance(record["entity_id"], str)
    assert isinstance(record["properties"], dict)
    assert isinstance(record["relationships"], dict)
    assert all(
        isinstance(ids, tuple) and all(isinstance(entity_id, str) for entity_id in ids)
        for ids in record["relationships"].values()
    )


def test_concrete_reader_exposes_only_contract_retrieval_methods() -> None:
    public_methods = {
        name
        for name, value in vars(Neo4jKnowledgeGraphReader).items()
        if not name.startswith("_") and callable(value)
    }
    retrieval_methods = public_methods - {"close"}

    assert retrieval_methods == {
        "get_project",
        "get_work_item",
        "list_project_technologies",
    }
    assert all(
        inspect.iscoroutinefunction(getattr(Neo4jKnowledgeGraphReader, name))
        for name in retrieval_methods
    )


def test_driver_uses_neo4j_configuration_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    import retrieval.graph as graph_module

    calls: list[tuple[str, tuple[str, str]]] = []
    driver = _Driver()

    def create_driver(uri: str, *, auth: tuple[str, str]) -> _Driver:
        calls.append((uri, auth))
        return driver

    monkeypatch.setattr(graph_module.AsyncGraphDatabase, "driver", create_driver)
    configuration = Settings(
        neo4j_uri="bolt://neo4j.example:7687",
        neo4j_username="atlas-user",
        neo4j_password="secret-value",
        neo4j_database="atlas",
    )

    reader = Neo4jKnowledgeGraphReader(configuration)

    assert calls == [("bolt://neo4j.example:7687", ("atlas-user", "secret-value"))]
    assert reader._settings.neo4j_database == "atlas"  # type: ignore[attr-defined]


def test_driver_rejects_missing_password_without_exposing_credentials() -> None:
    with pytest.raises(ValueError, match="Neo4j password must be configured") as error:
        Neo4jKnowledgeGraphReader(Settings())

    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_get_project_maps_properties_and_relationships() -> None:
    reader, driver = _reader(
        [
            [
                {
                    "project": {"id": "atlas", "name": "Atlas", "description": "Demo"},
                    "technology_ids": ["angular", "angular", "neo4j"],
                    "document_ids": ["atlas-overview"],
                    "work_item_ids": ["PBI-101", "PBI-102"],
                }
            ]
        ]
    )

    project = await reader.get_project("atlas")

    assert project is not None
    assert project == {
        "entity_type": "Project",
        "entity_id": "atlas",
        "properties": {"id": "atlas", "name": "Atlas", "description": "Demo"},
        "relationships": {
            "BELONGS_TO": ("PBI-101", "PBI-102"),
            "USES": ("angular", "neo4j"),
            "DOCUMENTED_BY": ("atlas-overview",),
        },
    }
    _assert_graph_record(project)
    query, parameters, database = driver.queries[0]
    assert "(project)-[:USES]->(technology:Technology)" in query
    assert "(project)-[:DOCUMENTED_BY]->(document:DocumentationArtifact)" in query
    assert "(work_item:WorkItem)-[:BELONGS_TO]->(project)" in query
    assert parameters == {"project_id": "atlas"}
    assert database == "atlas-test"
    assert len(driver.sessions) == 1
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_get_project_without_related_nodes_returns_empty_relationship_tuples() -> None:
    reader, driver = _reader(
        [
            [
                {
                    "project": {"id": "atlas", "name": "Atlas", "description": "Demo"},
                    "technology_ids": [],
                    "document_ids": [],
                    "work_item_ids": [],
                }
            ]
        ]
    )

    project = await reader.get_project("atlas")

    assert project == {
        "entity_type": "Project",
        "entity_id": "atlas",
        "properties": {"id": "atlas", "name": "Atlas", "description": "Demo"},
        "relationships": {
            "BELONGS_TO": (),
            "USES": (),
            "DOCUMENTED_BY": (),
        },
    }
    assert project is not None
    _assert_graph_record(project)
    assert len(driver.sessions) == 1
    assert driver.sessions[0].closed


@pytest.mark.asyncio
async def test_get_work_item_maps_all_relationships_and_empty_optional_values() -> None:
    reader, driver = _reader(
        [
            [
                {
                    "work_item": {"id": "PBI-102", "title": "Upgrade Angular"},
                    "project_ids": ["atlas"],
                    "assignee_ids": ["bob"],
                    "owner_ids": ["alice"],
                    "dependency_ids": ["PBI-101"],
                }
            ]
        ]
    )

    work_item = await reader.get_work_item("PBI-102")

    assert work_item is not None
    assert work_item["relationships"] == {
        "BELONGS_TO": ("atlas",),
        "ASSIGNED_TO": ("bob",),
        "OWNS": ("alice",),
        "DEPENDS_ON": ("PBI-101",),
    }
    _assert_graph_record(work_item)
    query, parameters, _ = driver.queries[0]
    assert "(work_item)-[:BELONGS_TO]->(project:Project)" in query
    assert "(work_item)-[:ASSIGNED_TO]->(assignee:Person)" in query
    assert "(owner:Person)-[:OWNS]->(work_item)" in query
    assert "(work_item)-[:DEPENDS_ON]->(dependency:WorkItem)" in query
    assert parameters == {"work_item_id": "PBI-102"}

    empty_reader, _ = _reader(
        [
            [
                {
                    "work_item": {"id": "PBI-103", "title": "Unassigned"},
                    "project_ids": [],
                    "assignee_ids": [],
                    "owner_ids": [],
                    "dependency_ids": [],
                }
            ]
        ]
    )
    empty_work_item = await empty_reader.get_work_item("PBI-103")
    assert empty_work_item is not None
    assert empty_work_item["relationships"] == {
        "BELONGS_TO": (),
        "ASSIGNED_TO": (),
        "OWNS": (),
        "DEPENDS_ON": (),
    }


@pytest.mark.asyncio
async def test_list_project_technologies_uses_project_to_technology_direction() -> None:
    reader, driver = _reader(
        [
            [
                {
                    "technology": {"id": "angular", "name": "Angular", "category": "framework"},
                    "project_ids": ["atlas", "atlas"],
                },
                {
                    "technology": {"id": "neo4j", "name": "Neo4j", "category": "database"},
                    "project_ids": ["atlas"],
                },
            ]
        ]
    )

    technologies = await reader.list_project_technologies("atlas")

    assert [technology["entity_id"] for technology in technologies] == ["angular", "neo4j"]
    assert technologies[0]["relationships"] == {"USES": ("atlas",)}
    for technology in technologies:
        _assert_graph_record(technology)

    query, parameters, _ = driver.queries[0]
    assert "(project:Project {id: $project_id})-[:USES]->(technology:Technology)" in query
    assert parameters == {"project_id": "atlas"}


@pytest.mark.asyncio
async def test_project_without_technologies_returns_empty_list() -> None:
    reader, _ = _reader([[]])

    assert await reader.list_project_technologies("atlas") == []


@pytest.mark.asyncio
async def test_missing_project_and_work_item_return_none() -> None:
    reader, driver = _reader([[], []])

    assert await reader.get_project("missing") is None
    assert await reader.get_work_item("missing") is None
    assert [parameters for _, parameters, _ in driver.queries] == [
        {"project_id": "missing"},
        {"work_item_id": "missing"},
    ]


@pytest.mark.asyncio
async def test_reader_only_runs_parameterized_read_queries_and_closes_driver() -> None:
    reader, driver = _reader(
        [
            [
                {
                    "work_item": {"id": "PBI-102", "title": "Upgrade Angular"},
                    "project_ids": [],
                    "assignee_ids": [],
                    "owner_ids": [],
                    "dependency_ids": [],
                }
            ]
        ]
    )

    await reader.get_work_item("PBI-102' MATCH (n) DETACH DELETE n //")

    query, parameters, _ = driver.queries[0]
    assert "PBI-102" not in query
    assert parameters == {
        "work_item_id": "PBI-102' MATCH (n) DETACH DELETE n //"
    }
    assert not any(
        keyword in query.upper()
        for keyword in ("CREATE ", "MERGE ", "DELETE ", " SET ", "REMOVE ")
    )

    await reader.close()
    assert driver.closed
