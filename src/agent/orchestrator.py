"""Invocation boundary for the central agent graph."""

import asyncio
import inspect
import threading
from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import Future
from typing import Any, Protocol, TypeVar

from openai import AsyncOpenAI

from config.settings import Settings, settings
from retrieval.adapters import KnowledgeGraphReader, RAGReader

from .graph import (
    AgentNode,
    ChatClient,
    build_agent_graph,
    build_informational_agent_graph,
)

T = TypeVar("T")


class CompiledAgent(Protocol):
    """Subset of a compiled LangGraph used by the orchestration boundary."""

    async def ainvoke(self, input: Mapping[str, Any]) -> Mapping[str, Any]:
        """Asynchronously invoke the graph for one user input."""
        ...


class _PersistentAsyncLoop:
    """Run all orchestrator coroutines on one owned event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    def run(self, coroutine: Awaitable[T]) -> T:
        """Run a coroutine on the persistent loop and wait for its result."""
        return self._submit(coroutine).result()

    async def run_async(self, coroutine: Awaitable[T]) -> T:
        """Await a coroutine running on the persistent loop from another loop."""
        return await asyncio.wrap_future(self._submit(coroutine))

    def close(self, cleanup: Callable[[], Awaitable[object]] | None = None) -> None:
        """Run resource cleanup on the loop, then stop and join its thread."""
        with self._lock:
            if self._closed:
                return
            if cleanup is None and self._loop is None:
                self._closed = True
                return
            if self._loop is None:
                self._start_locked()
            self._closed = True
            loop = self._loop
            thread = self._thread

        cleanup_error: BaseException | None = None
        try:
            if cleanup is not None:
                assert loop is not None
                asyncio.run_coroutine_threadsafe(cleanup(), loop).result()
        except BaseException as error:
            cleanup_error = error
        finally:
            if loop is not None and thread is not None:
                loop.call_soon_threadsafe(loop.stop)
                thread.join()
        if cleanup_error is not None:
            raise cleanup_error

    def _submit(self, coroutine: Awaitable[T]) -> Future[T]:
        with self._lock:
            if self._closed:
                if inspect.iscoroutine(coroutine):
                    coroutine.close()
                raise RuntimeError("The agent orchestrator has been closed.")
            if self._loop is None:
                self._start_locked()
            loop = self._loop
            thread = self._thread

        if thread is not None and threading.current_thread() is thread:
            if inspect.iscoroutine(coroutine):
                coroutine.close()
            raise RuntimeError("The synchronous loop runner cannot submit work to itself.")
        if loop is None:
            if inspect.iscoroutine(coroutine):
                coroutine.close()
            raise RuntimeError("The agent event loop failed to start.")
        return asyncio.run_coroutine_threadsafe(coroutine, loop)

    def _start_locked(self) -> None:
        self._started.clear()

        def run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._started.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
                asyncio.set_event_loop(None)

        self._thread = threading.Thread(target=run_loop, name="projectops-agent-loop", daemon=True)
        self._thread.start()
        self._started.wait()


class AgentOrchestrator:
    """Forward user input to a compiled agent graph and return its response."""

    def __init__(
        self,
        graph: CompiledAgent,
        *,
        resources: tuple[object, ...] = (),
    ) -> None:
        self._graph = graph
        self._resources = resources
        self._loop = _PersistentAsyncLoop()
        self._operation_lock: asyncio.Lock | None = None

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
        resources = (llm_client, rag_reader, knowledge_graph_reader)
        return cls(graph, resources=resources)

    def invoke(self, user_input: str) -> str:
        """Send input through the graph and return its generated response."""
        return self._loop.run(self._invoke_on_loop(user_input))

    async def ainvoke(self, user_input: str) -> str:
        """Invoke the graph on its owned loop from an existing event loop."""
        return await self._loop.run_async(self._invoke_on_loop(user_input))

    async def _invoke_on_loop(self, user_input: str) -> str:
        if self._operation_lock is None:
            self._operation_lock = asyncio.Lock()
        async with self._operation_lock:
            return await self._invoke_graph(user_input)

    async def _invoke_graph(self, user_input: str) -> str:
        state = await self._graph.ainvoke({"user_input": user_input})
        response = state.get("response")
        if not isinstance(response, str):
            raise RuntimeError("The agent graph did not return a string response.")
        return response

    async def _close_resources(self) -> object:
        if self._operation_lock is None:
            self._operation_lock = asyncio.Lock()
        async with self._operation_lock:
            closed: set[int] = set()
            for resource in self._resources:
                if id(resource) in closed:
                    continue
                closed.add(id(resource))
                close = getattr(resource, "aclose", None)
                if not callable(close):
                    close = getattr(resource, "close", None)
                if callable(close):
                    result = close()
                    if inspect.isawaitable(result):
                        await result
        return None

    def close(self) -> None:
        """Close supported async resources and stop the owned event-loop thread."""
        cleanup = self._close_resources if self._resources else None
        self._loop.close(cleanup)

    def __enter__(self) -> "AgentOrchestrator":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
