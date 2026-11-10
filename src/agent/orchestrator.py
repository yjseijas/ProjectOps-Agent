"""Invocation boundary for the central agent graph."""

from collections.abc import Mapping
from typing import Any, Protocol

from .graph import AgentNode, build_agent_graph


class CompiledAgent(Protocol):
    """Subset of a compiled LangGraph used by the orchestration boundary."""

    def invoke(self, input: Mapping[str, Any]) -> Mapp+--------------------------ing[str, Any]:
        """Invoke the graph for one user input."""
        ...


class AgentOrchestrator:
    """Forward user input to a compiled agent graph and return its response."""

    def __init__(self, graph: CompiledAgent) -> None:
        self._graph = graph

    @classmethod
    def from_node(cls, agent_node: AgentNode) -> "AgentOrchestrator":
        """Construct an orchestrator from an injected graph node."""
        return cls(build_agent_graph(agent_node))

    def invoke(self, user_input: str) -> str:
        """Send input through the graph without classifying or routing the request."""
        state = self._graph.invoke({"user_input": user_input})
        response = state.get("response")
        if not isinstance(response, str):
            raise RuntimeError("The agent graph did not return a string response.")
        return response
