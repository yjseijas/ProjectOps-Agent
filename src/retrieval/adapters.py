"""Read-only contracts for informational retrieval adapters."""

from typing import Protocol, TypedDict


class RetrievedDocument(TypedDict):
    """A document passage returned by a RAG implementation."""

    id: str
    title: str
    content: str
    source: str


class GraphRecord(TypedDict):
    """A structured fact returned by a Knowledge Graph implementation."""

    entity_type: str
    entity_id: str
    properties: dict[str, object]
    relationships: dict[str, tuple[str, ...]]


class RAGReader(Protocol):
    """Read-only document search capability."""

    async def search_documents(
        self, query: str, *, limit: int = 5
    ) -> list[RetrievedDocument]:
        """Return relevant document passages without changing corpus state."""
        ...


class KnowledgeGraphReader(Protocol):
    """Read-only structured project information capability."""

    async def get_project(self, project_id: str) -> GraphRecord | None:
        """Return a project and its recorded relationships, if present."""
        ...

    async def get_work_item(self, work_item_id: str) -> GraphRecord | None:
        """Return a work item and its recorded relationships, if present."""
        ...

    async def list_project_technologies(self, project_id: str) -> list[GraphRecord]:
        """Return technologies associated with a project."""
        ...
