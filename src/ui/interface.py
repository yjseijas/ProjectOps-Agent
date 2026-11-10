"""Passive terminal interface that forwards messages and renders responses."""

from collections.abc import Callable
from typing import Protocol


class AgentInterface(Protocol):
    """Only the agent invocation needed by the passive UI."""

    def invoke(self, user_input: str) -> str:
        """Forward a user message and return the agent's response."""
        ...


def run_cli(
    agent: AgentInterface,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], object] = print,
) -> None:
    """Read messages, forward them unchanged, and render returned responses."""
    while True:
        try:
            user_input = input_fn("> ")
        except EOFError:
            return
        if not user_input.strip():
            continue
        output_fn(agent.invoke(user_input))
