"""Connection and invocation contract for an MCP client implementation."""

from typing import Protocol, TypedDict


class MCPToolResult(TypedDict, total=False):
    """Transport-neutral representation of an MCP tool result."""

    content: list[object]
    structured_content: dict[str, object]
    is_error: bool


class MCPClient(Protocol):
    """Minimal client lifecycle and tool-call interface."""

    async def connect(self) -> None:
        """Establish a connection to an independently running MCP server."""
        ...

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> MCPToolResult:
        """Invoke a named server tool; this interface does not define business tools."""
        ...

    async def close(self) -> None:
        """Release the client connection."""
        ...
