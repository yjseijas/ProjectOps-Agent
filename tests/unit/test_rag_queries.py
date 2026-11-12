from types import SimpleNamespace

import pytest

from config.settings import Settings
from data.atlas_seed import ATLAS_DOCUMENTS
from retrieval.rag import QdrantRAGReader


class _OpenAIEmbeddingClient:
    def __init__(self) -> None:
        self.embeddings = self
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[float(index), 1.0])
                for index, _ in enumerate(input)
            ]
        )


class _QdrantClient:
    def __init__(self) -> None:
        self.exists = False
        self.created_collection: dict[str, object] | None = None
        self.points: list[object] = []
        self.query: dict[str, object] | None = None
        self.query_results = SimpleNamespace(points=[])

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def create_collection(self, **kwargs: object) -> None:
        self.created_collection = kwargs
        self.exists = True

    async def upsert(self, *, points: list[object], **kwargs: object) -> None:
        self.points = points

    async def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.query = kwargs
        return self.query_results


def _reader() -> tuple[QdrantRAGReader, _OpenAIEmbeddingClient, _QdrantClient]:
    embeddings = _OpenAIEmbeddingClient()
    qdrant = _QdrantClient()
    reader = QdrantRAGReader(
        Settings(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            qdrant_collection="atlas-documents",
        ),
        openai_client=embeddings,  # type: ignore[arg-type]
        qdrant_client=qdrant,  # type: ignore[arg-type]
    )
    return reader, embeddings, qdrant


@pytest.mark.asyncio
async def test_ingest_atlas_documents_embeds_and_upserts_seed_corpus() -> None:
    reader, embeddings, qdrant = _reader()

    ingested = await reader.ingest_atlas_documents()

    assert ingested == len(ATLAS_DOCUMENTS)
    assert embeddings.calls == [
        {
            "model": "text-embedding-3-small",
            "input": [document.content for document in ATLAS_DOCUMENTS],
        }
    ]
    assert qdrant.created_collection is not None
    assert qdrant.created_collection["collection_name"] == "atlas-documents"
    assert qdrant.created_collection["vectors_config"].size == 2  # type: ignore[attr-defined]
    assert len(qdrant.points) == len(ATLAS_DOCUMENTS)
    assert [
        point.payload["id"]
        for point in qdrant.points  # type: ignore[attr-defined]
    ] == [document.id for document in ATLAS_DOCUMENTS]


@pytest.mark.asyncio
async def test_search_documents_embeds_query_and_returns_retrieved_document() -> None:
    reader, embeddings, qdrant = _reader()
    qdrant.query_results = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "id": "atlas-deployment",
                    "title": "Atlas Deployment Guide",
                    "content": "Keep provider credentials in local environment variables.",
                    "source": "atlas-deployment",
                }
            )
        ]
    )

    documents = await reader.search_documents("Atlas deployment", limit=2)

    assert embeddings.calls == [{"model": "text-embedding-3-small", "input": ["Atlas deployment"]}]
    assert qdrant.query == {
        "collection_name": "atlas-documents",
        "query": [0.0, 1.0],
        "limit": 2,
        "with_payload": True,
    }
    assert documents == [
        {
            "id": "atlas-deployment",
            "title": "Atlas Deployment Guide",
            "content": "Keep provider credentials in local environment variables.",
            "source": "atlas-deployment",
        }
    ]


@pytest.mark.asyncio
async def test_search_documents_rejects_nonpositive_limit() -> None:
    reader, embeddings, _ = _reader()

    with pytest.raises(ValueError, match="limit must be greater than zero"):
        await reader.search_documents("Atlas deployment", limit=0)

    assert embeddings.calls == []


@pytest.mark.asyncio
async def test_search_documents_defaults_to_five_results() -> None:
    reader, _, qdrant = _reader()

    await reader.search_documents("Atlas deployment")

    assert qdrant.query is not None
    assert qdrant.query["limit"] == 5


def test_embedding_defaults_are_independent_from_chat_model() -> None:
    configuration = Settings()

    assert configuration.embedding_provider == "openai"
    assert configuration.embedding_model == "text-embedding-3-small"
    assert configuration.llm_model == "gpt-4o-mini"
