"""Read-only Neo4j retrieval for structured Atlas project information."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from neo4j import AsyncDriver, AsyncGraphDatabase

from config.settings import Settings, settings
from retrieval.adapters import GraphRecord


_PROJECT_QUERY = """
MATCH (project:Project {id: $project_id})
OPTIONAL MATCH (project)-[:USES]->(technology:Technology)
WITH project, collect(DISTINCT technology.id) AS technology_ids
OPTIONAL MATCH (project)-[:DOCUMENTED_BY]->(document:DocumentationArtifact)
WITH project, technology_ids, collect(DISTINCT document.id) AS document_ids
OPTIONAL MATCH (work_item:WorkItem)-[:BELONGS_TO]->(project)
RETURN project,
       technology_ids,
       document_ids,
       collect(DISTINCT work_item.id) AS work_item_ids
"""

_WORK_ITEM_QUERY = """
MATCH (work_item:WorkItem {id: $work_item_id})
OPTIONAL MATCH (work_item)-[:BELONGS_TO]->(project:Project)
WITH work_item, collect(DISTINCT project.id) AS project_ids
OPTIONAL MATCH (work_item)-[:ASSIGNED_TO]->(assignee:Person)
WITH work_item, project_ids, collect(DISTINCT assignee.id) AS assignee_ids
OPTIONAL MATCH (owner:Person)-[:OWNS]->(work_item)
WITH work_item, project_ids, assignee_ids, collect(DISTINCT owner.id) AS owner_ids
OPTIONAL MATCH (work_item)-[:DEPENDS_ON]->(dependency:WorkItem)
RETURN work_item,
       project_ids,
       assignee_ids,
       owner_ids,
       collect(DISTINCT dependency.id) AS dependency_ids
"""

_PROJECT_TECHNOLOGIES_QUERY = """
MATCH (project:Project {id: $project_id})-[:USES]->(technology:Technology)
RETURN technology, collect(DISTINCT project.id) AS project_ids
ORDER BY technology.id
"""


class Neo4jKnowledgeGraphReader:
    """Read project, work-item, and technology facts from Neo4j."""

    def __init__(
        self,
        configuration: Settings = settings,
        *,
        driver: AsyncDriver | None = None,
    ) -> None:
        self._settings = configuration
        self._driver = driver if driver is not None else self._create_driver(configuration)

    @staticmethod
    def _create_driver(configuration: Settings) -> AsyncDriver:
        password = configuration.neo4j_password
        if password is None or not password.get_secret_value():
            raise ValueError("Neo4j password must be configured")
        if not configuration.neo4j_uri.strip():
            raise ValueError("Neo4j URI must not be empty")
        if not configuration.neo4j_username.strip():
            raise ValueError("Neo4j username must not be empty")
        if not configuration.neo4j_database.strip():
            raise ValueError("Neo4j database must not be empty")

        return AsyncGraphDatabase.driver(
            configuration.neo4j_uri,
            auth=(configuration.neo4j_username, password.get_secret_value()),
        )

    async def get_project(self, project_id: str) -> GraphRecord | None:
        async with self._driver.session(database=self._settings.neo4j_database) as session:
            result = await session.run(_PROJECT_QUERY, project_id=project_id)
            record = await result.single()

        if record is None:
            return None

        return self._as_graph_record(
            "Project",
            record["project"],
            {
                "BELONGS_TO": record["work_item_ids"],
                "USES": record["technology_ids"],
                "DOCUMENTED_BY": record["document_ids"],
            },
        )

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        async with self._driver.session(database=self._settings.neo4j_database) as session:
            result = await session.run(_WORK_ITEM_QUERY, work_item_id=work_item_id)
            record = await result.single()

        if record is None:
            return None

        return self._as_graph_record(
            "WorkItem",
            record["work_item"],
            {
                "BELONGS_TO": record["project_ids"],
                "ASSIGNED_TO": record["assignee_ids"],
                "OWNS": record["owner_ids"],
                "DEPENDS_ON": record["dependency_ids"],
            },
        )

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        async with self._driver.session(database=self._settings.neo4j_database) as session:
            result = await session.run(_PROJECT_TECHNOLOGIES_QUERY, project_id=project_id)
            records = await result.data()

        return [
            self._as_graph_record(
                "Technology",
                record["technology"],
                {"USES": record["project_ids"]},
            )
            for record in records
        ]

    async def close(self) -> None:
        """Close the shared driver when the reader's application lifecycle ends."""
        await self._driver.close()

    async def __aenter__(self) -> Neo4jKnowledgeGraphReader:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @staticmethod
    def _as_graph_record(
        entity_type: str,
        node: Mapping[str, object],
        relationships: Mapping[str, object],
    ) -> GraphRecord:
        properties = dict(node)
        entity_id = properties.get("id")
        if not isinstance(entity_id, str):
            raise RuntimeError(f"Neo4j returned a {entity_type} node without a string id")

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "properties": properties,
            "relationships": {
                name: Neo4jKnowledgeGraphReader._as_id_tuple(name, values)
                for name, values in relationships.items()
            },
        }

    @staticmethod
    def _as_id_tuple(relationship: str, values: object) -> tuple[str, ...]:
        if not isinstance(values, (list, tuple)):
            raise RuntimeError(f"Neo4j returned invalid IDs for {relationship}")
        if not all(isinstance(value, str) for value in values):
            raise RuntimeError(f"Neo4j returned invalid IDs for {relationship}")
        return tuple(sorted(set(cast(list[str] | tuple[str, ...], values))))
