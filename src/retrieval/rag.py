"""OpenAI-embedding-backed document retrieval from Qdrant."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models

from config.settings import Settings, settings
from data.atlas_seed import ATLAS_DOCUMENTS, DocumentationSeed
from retrieval.adapters import RetrievedDocument


class QdrantRAGReader:
    """Embed Atlas documents and queries with OpenAI and retrieve them from Qdrant."""

    def __init__(
        self,
        configuration: Settings = settings,
        *,
        openai_client: AsyncOpenAI | None = None,
        qdrant_client: AsyncQdrantClient | None = None,
    ) -> None:
        if configuration.embedding_provider.casefold() != "openai":
            raise ValueError(f"Unsupported embedding provider: {configuration.embedding_provider}")

        self._settings = configuration
        embedding_api_key = configuration.embedding_api_key
        if embedding_api_key is None or not embedding_api_key.get_secret_value():
            embedding_api_key = configuration.llm_api_key
        openai_api_key = (
            embedding_api_key.get_secret_value() if embedding_api_key is not None else None
        )
        qdrant_api_key = (
            configuration.qdrant_api_key.get_secret_value()
            if configuration.qdrant_api_key is not None
            else None
        )
        self._openai = (
            openai_client
            if openai_client is not None
            else AsyncOpenAI(api_key=openai_api_key or None)
        )
        self._qdrant = (
            qdrant_client
            if qdrant_client is not None
            else AsyncQdrantClient(
                url=configuration.qdrant_url,
                api_key=qdrant_api_key or None,
            )
        )

    async def ingest_atlas_documents(self) -> int:
        """Upsert the seeded Atlas documentation into the configured collection."""
        return await self.ingest_documents(ATLAS_DOCUMENTS)

    async def ingest_documents(self, documents: Sequence[DocumentationSeed]) -> int:
        """Embed and upsert documents, using deterministic Qdrant point IDs."""
        if not documents:
            return 0

        vectors = await self._embed_texts([document.content for document in documents])
        collection_name = self._settings.qdrant_collection
        if not await self._qdrant.collection_exists(collection_name):
            await self._qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=len(vectors[0]),
                    distance=models.Distance.COSINE,
                ),
            )

        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, document.id)),
                vector=vector,
                payload={
                    "id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "source": document.id,
                },
            )
            for document, vector in zip(documents, vectors, strict=True)
        ]
        await self._qdrant.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
        return len(points)

    async def search_documents(self, query: str, *, limit: int = 5) -> list[RetrievedDocument]:
        """Return the closest document passages for an embedded query."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        query_vector = (await self._embed_texts([query]))[0]
        response = await self._qdrant.query_points(
            collection_name=self._settings.qdrant_collection,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        return [self._as_retrieved_document(point.payload) for point in response.points]

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self._openai.embeddings.create(
            model=self._settings.embedding_model,
            input=texts,
        )
        embeddings = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"OpenAI returned {len(embeddings)} embeddings for {len(texts)} inputs"
            )
        return embeddings

    @staticmethod
    def _as_retrieved_document(payload: dict[str, object] | None) -> RetrievedDocument:
        if payload is None:
            raise ValueError("Qdrant returned a document with an invalid payload")

        document_id = payload.get("id")
        title = payload.get("title")
        content = payload.get("content")
        source = payload.get("source")
        if (
            not isinstance(document_id, str)
            or not isinstance(title, str)
            or not isinstance(content, str)
            or not isinstance(source, str)
        ):
            raise ValueError("Qdrant returned a document with an invalid payload")

        return {
            "id": document_id,
            "title": title,
            "content": content,
            "source": source,
        }
