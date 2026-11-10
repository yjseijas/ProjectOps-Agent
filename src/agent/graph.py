"""Minimal LangGraph structure with an injected, non-routing agent node."""

from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict, total=False):
    """State passed through the central orchestration graph."""

    user_input: str
    response: str


AgentNode = Callable[[AgentState], Mapping[str, Any]]


def build_agent_graph(agent_node: AgentNode):
    """Build a single-node graph; capability selection is intentionally not defined."""
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()
