"""Central LangGraph for read-only informational retrieval."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from json import dumps, loads
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from retrieval.adapters import KnowledgeGraphReader, RAGReader

from .prompts import INFORMATIONAL_AGENT_PROMPT


class AgentState(TypedDict, total=False):
    """State passed through the central orchestration graph."""

    user_input: str
    messages: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, str]]
    response: str


AgentNode = Callable[[AgentState], Mapping[str, Any]]


class ChatCompletions(Protocol):
    """OpenAI-compatible asynchronous chat-completions endpoint."""

    async def create(self, **kwargs: object) -> object:
        """Create a chat completion."""
        ...


class ChatEndpoint(Protocol):
    """Chat namespace containing the completion endpoint."""

    completions: ChatCompletions


class ChatClient(Protocol):
    """Minimal LLM client interface used by the agent graph."""

    chat: ChatEndpoint


class ToolHandler(Protocol):
    """An asynchronous read-only retrieval operation."""

    def __call__(self, arguments: Mapping[str, object]) -> Awaitable[object]: ...


_INFORMATIONAL_TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search project documentation for passages relevant to a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project",
            "description": "Retrieve a project and its recorded relationships by project ID.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_item",
            "description": "Retrieve a work item and its recorded relationships by work-item ID.",
            "parameters": {
                "type": "object",
                "properties": {"work_item_id": {"type": "string"}},
                "required": ["work_item_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_project_technologies",
            "description": "List technologies associated with a project ID.",
            "parameters": {
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    },
]


def build_agent_graph(agent_node: AgentNode):
    """Build the existing single-node graph for an injected agent node."""
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph.compile()


def build_informational_agent_graph(
    *,
    llm_client: ChatClient,
    rag_reader: RAGReader,
    knowledge_graph_reader: KnowledgeGraphReader,
    model: str,
):
    """Build an LLM-directed LangGraph for read-only retrieval and response generation."""
    completions: ChatCompletions = llm_client.chat.completions
    handlers = _create_tool_handlers(rag_reader, knowledge_graph_reader)

    async def agent_node(state: AgentState) -> dict[str, Any]:
        messages = state.get("messages")
        if messages is None:
            user_input = state.get("user_input")
            if not isinstance(user_input, str):
                raise ValueError("The agent graph requires a string user_input.")
            messages = [
                {"role": "system", "content": INFORMATIONAL_AGENT_PROMPT},
                {"role": "user", "content": user_input},
            ]

        completion = await completions.create(
            model=model,
            messages=messages,
            tools=_INFORMATIONAL_TOOLS,
            tool_choice="auto",
        )
        choices = _field(completion, "choices")
        if not isinstance(choices, Sequence) or not choices:
            raise RuntimeError("The LLM returned no completion choices.")
        message = _field(choices[0], "message")
        content = _field(message, "content")
        tool_calls = _field(message, "tool_calls")

        if tool_calls:
            if not isinstance(tool_calls, Sequence):
                raise RuntimeError("The LLM returned invalid tool calls.")
            normalized_calls = [_normalize_tool_call(call) for call in tool_calls]
            assistant_message = {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        },
                    }
                    for call in normalized_calls
                ],
            }
            return {
                "messages": [*messages, assistant_message],
                "pending_tool_calls": normalized_calls,
            }

        if not isinstance(content, str):
            raise RuntimeError("The LLM returned neither a response nor tool calls.")
        return {"messages": messages, "pending_tool_calls": [], "response": content}

    async def retrieval_node(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        for call in state.get("pending_tool_calls", []):
            handler = handlers.get(call["name"])
            if handler is None:
                raise RuntimeError(f"The LLM requested an unavailable tool: {call['name']}")
            arguments = _parse_arguments(call["arguments"], call["name"])
            result = await handler(arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": dumps(result, ensure_ascii=False),
                }
            )
        return {"messages": messages, "pending_tool_calls": []}

    def next_node(state: AgentState) -> str:
        return "retrieve" if state.get("pending_tool_calls") else END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", next_node, {"retrieve": "retrieve", END: END})
    graph.add_edge("retrieve", "agent")
    return graph.compile()


def _create_tool_handlers(
    rag_reader: RAGReader,
    knowledge_graph_reader: KnowledgeGraphReader,
) -> dict[str, ToolHandler]:
    async def search_documents(arguments: Mapping[str, object]) -> object:
        _check_keys(arguments, {"query", "limit"}, {"query"})
        query = _required_string(arguments, "query")
        limit = arguments.get("limit", 5)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("search_documents limit must be a positive integer.")
        return await rag_reader.search_documents(query, limit=limit)

    async def get_project(arguments: Mapping[str, object]) -> object:
        _check_keys(arguments, {"project_id"}, {"project_id"})
        return await knowledge_graph_reader.get_project(_required_string(arguments, "project_id"))

    async def get_work_item(arguments: Mapping[str, object]) -> object:
        _check_keys(arguments, {"work_item_id"}, {"work_item_id"})
        return await knowledge_graph_reader.get_work_item(
            _required_string(arguments, "work_item_id")
        )

    async def list_project_technologies(arguments: Mapping[str, object]) -> object:
        _check_keys(arguments, {"project_id"}, {"project_id"})
        return await knowledge_graph_reader.list_project_technologies(
            _required_string(arguments, "project_id")
        )

    return {
        "search_documents": search_documents,
        "get_project": get_project,
        "get_work_item": get_work_item,
        "list_project_technologies": list_project_technologies,
    }


def _normalize_tool_call(tool_call: object) -> dict[str, str]:
    call_id = _field(tool_call, "id")
    function = _field(tool_call, "function")
    name = _field(function, "name")
    arguments = _field(function, "arguments")
    if not all(isinstance(value, str) for value in (call_id, name, arguments)):
        raise RuntimeError("The LLM returned a malformed tool call.")
    return {"id": call_id, "name": name, "arguments": arguments}


def _parse_arguments(arguments: str, tool_name: str) -> Mapping[str, object]:
    parsed = loads(arguments)
    if not isinstance(parsed, Mapping):
        raise ValueError(f"The LLM supplied invalid arguments for {tool_name}.")
    return parsed


def _check_keys(
    arguments: Mapping[str, object],
    allowed: set[str],
    required: set[str],
) -> None:
    if not required.issubset(arguments) or not set(arguments).issubset(allowed):
        raise ValueError("The LLM supplied arguments that do not match the retrieval tool schema.")


def _required_string(arguments: Mapping[str, object], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"The retrieval tool requires a non-empty {name}.")
    return value


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)
