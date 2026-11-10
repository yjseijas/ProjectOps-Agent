"""Small, in-memory Atlas domain fixture definitions.

These records describe seed data only. They do not connect to or write to a
database, vector store, or MCP server.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


WorkItemStatus = Literal["Backlog", "In Progress", "Done", "Blocked"]


class SeedRecord(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProjectSeed(SeedRecord):
    id: str
    name: str
    description: str
    technology_ids: tuple[str, ...]
    documentation_ids: tuple[str, ...]


class PersonSeed(SeedRecord):
    id: str
    name: str
    role: str
    project_ids: tuple[str, ...]
    owned_work_item_ids: tuple[str, ...] = ()


class WorkItemSeed(SeedRecord):
    id: str
    title: str
    project_id: str
    assignee_id: str | None = None
    owner_id: str | None = None
    status: WorkItemStatus = "Backlog"
    dependency_ids: tuple[str, ...] = ()
    description: str


class TechnologySeed(SeedRecord):
    id: str
    name: str
    category: str
    project_ids: tuple[str, ...]


class DocumentationSeed(SeedRecord):
    id: str
    title: str
    project_id: str
    section: str
    content: str
    tags: tuple[str, ...] = ()


ATLAS_PROJECT = ProjectSeed(
    id="atlas",
    name="Atlas",
    description="A fictional project used to demonstrate ProjectOps capabilities.",
    technology_ids=("dotnet10", "angular", "neo4j", "docker"),
    documentation_ids=("atlas-overview", "atlas-deployment", "atlas-migration"),
)

ATLAS_PEOPLE = (
    PersonSeed(
        id="alice",
        name="Alice",
        role="Backend Engineer",
        project_ids=("atlas",),
        owned_work_item_ids=("PBI-101",),
    ),
    PersonSeed(
        id="bob",
        name="Bob",
        role="Frontend Engineer",
        project_ids=("atlas",),
    ),
)

ATLAS_WORK_ITEMS = (
    WorkItemSeed(
        id="PBI-101",
        title="Plan Atlas API migration",
        project_id="atlas",
        assignee_id="alice",
        owner_id="alice",
        status="In Progress",
        description="Plan the service and compatibility requirements for the API migration.",
    ),
    WorkItemSeed(
        id="PBI-102",
        title="Upgrade Angular application",
        project_id="atlas",
        assignee_id="bob",
        owner_id="alice",
        status="Backlog",
        dependency_ids=("PBI-101",),
        description="Upgrade the Atlas web application to the supported Angular release.",
    ),
)

ATLAS_TECHNOLOGIES = (
    TechnologySeed(
        id="dotnet10",
        name=".NET 10",
        category="framework",
        project_ids=("atlas",),
    ),
    TechnologySeed(
        id="angular",
        name="Angular",
        category="framework",
        project_ids=("atlas",),
    ),
    TechnologySeed(
        id="neo4j",
        name="Neo4j",
        category="database",
        project_ids=("atlas",),
    ),
    TechnologySeed(
        id="docker",
        name="Docker",
        category="infrastructure",
        project_ids=("atlas",),
    ),
)

ATLAS_DOCUMENTS = (
    DocumentationSeed(
        id="atlas-overview",
        title="Atlas Project Overview",
        project_id="atlas",
        section="overview",
        content="Atlas is a fictional software project for demonstrating project operations.",
        tags=("project", "overview"),
    ),
    DocumentationSeed(
        id="atlas-deployment",
        title="Atlas Deployment Guide",
        project_id="atlas",
        section="deployment",
        content=(
            "The local demo requires Python 3.11 or newer, Neo4j, and a vector store. "
            "Keep provider credentials in local environment variables."
        ),
        tags=("deployment", "local", "requirements"),
    ),
    DocumentationSeed(
        id="atlas-migration",
        title="Atlas API Migration Notes",
        project_id="atlas",
        section="architecture",
        content=(
            "The API migration plan should preserve compatibility for existing clients "
            "and coordinate service and application changes."
        ),
        tags=("migration", "api", "architecture"),
    ),
)
