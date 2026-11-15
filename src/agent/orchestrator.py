"""Invocation boundary for the central agent graph."""

import asyncio
from collections.abc import Mapping
from typing import Any, Protocol

from openai import AsyncOpenAI

from config.settings import Settings, settings
from retrieval.adapters import KnowledgeGraphReader, RAGReader

from .graph import (
    AgentNode,
    ChatClient,
    build_agent_graph,
    build_informational_agent_graph,
)


class CompiledAgent(Protocol):
    """Subset of a compiled LangGraph used by the orchestration boundary."""

    async def ainvoke(self, input: Mapping[str, Any]) -> Mapping[str, Any]:
        """Asynchronously invoke the graph for one user input."""
        ...


class AgentOrchestrator:
    """Forward user input to a compiled agent graph and return its response."""

    def __init__(self, graph: CompiledAgent) -> None:
        self._graph = graph

    @classmethod
    def from_node(cls, agent_node: AgentNode) -> "AgentOrchestrator":
        """Construct an orchestrator from an injected graph node."""
        return cls(build_agent_graph(agent_node))

    @classmethod
    def from_readers(
        cls,
        rag_reader: RAGReader,
        knowledge_graph_reader: KnowledgeGraphReader,
        *,
        llm_client: ChatClient | None = None,
        configuration: Settings = settings,
    ) -> "AgentOrchestrator":
        """Construct the centralized LLM agent with its read-only retrieval adapters."""
        if llm_client is None:
            if configuration.llm_provider.casefold() != "openai":
                raise ValueError(f"Unsupported LLM provider: {configuration.llm_provider}")
            api_key = (
                configuration.llm_api_key.get_secret_value()
                if configuration.llm_api_key is not None
                else None
            )
            llm_client = AsyncOpenAI(api_key=api_key or None)

        graph = build_informational_agent_graph(
            llm_client=llm_client,
            rag_reader=rag_reader,
            knowledge_graph_reader=knowledge_graph_reader,
            model=configuration.llm_model,
        )
        return cls(graph)

    def invoke(self, user_input: str) -> str:
        """Send input through the graph and return its generated response."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ainvoke(user_input))
        else:
            raise RuntimeError(
                "invoke() cannot run inside an active event loop; use await ainvoke() instead."
            )

    async def ainvoke(self, user_input: str) -> str:
        """Asynchronously invoke the graph for applications already using an event loop."""
        state = await self._graph.ainvoke({"user_input": user_input})
        response = state.get("response")
        if not isinstance(response, str):
            raise RuntimeError("The agent graph did not return a string response.")
        return response
