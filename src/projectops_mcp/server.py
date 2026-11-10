"""Independently runnable MCP server shell with no business tools registered."""


def create_server():
    """Create the MCP server shell without retrieval or action implementations."""
    from mcp.server.fastmcp import FastMCP

    return FastMCP("ProjectOps Actions")


def main() -> None:
    """Run the empty server over stdio for future MCP tool registration."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
