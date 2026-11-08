# Quickstart

## Prerequisites

- Python 3.11+
- Docker or local services for Neo4j and the vector store
- A working LLM provider configuration for the LangGraph agent
- MCP-compatible server runtime for the action layer

## Setup

1. Create a virtual environment and install project dependencies.
2. Start the Neo4j instance with the Atlas seed dataset.
3. Start the vector database and ingest the Atlas documentation corpus.
4. Launch the MCP server process with the action tool definitions.
5. Start the LangGraph orchestrator with access to both retrieval adapters and the MCP client tools.

## Application processes

The application consists of two independently executable processes:

1. MCP Server:
   - Starts independently of the LangGraph agent.
   - Connects to the persistent Atlas data store.
   - Exposes action tools through the MCP protocol.
   - Does not provide informational retrieval capabilities.

2. LangGraph Agent:
   - Starts the central agent orchestration pipeline.
   - Connects to the RAG and Knowledge Graph retrieval adapters.
   - Connects to the independently running MCP Server.
   - Discovers available MCP tools at runtime.
   - Receives user messages and generates responses.

The user interface communicates only with the LangGraph Agent.
It does not communicate directly with the MCP Server or retrieval databases.

## Validation scenarios

### Informational request via RAG

Ask: "What are the deployment requirements for the Atlas project?"

Expected result:

- The LLM-powered agent determines that document retrieval is required and invokes the RAG capability.
- The answer is grounded in deployment documentation.
- No action tool is called.

### Informational request via knowledge graph

Ask: "Who is assigned to PBI-102?"

Expected result:

- The LLM-powered agent determines that structured project information is required and invokes the Knowledge Graph capability.
- The answer is produced from the graph relationship between WorkItem and Person.
- No state change occurs.

### Combined retrieval

Ask: "Who owns the Atlas API migration and what does the migration documentation say about it?"

Expected result:

- The orchestrator uses the graph to determine ownership and the document corpus to retrieve migration guidance.
- The final answer synthesizes both sources in one response.

### Action request via MCP

Ask: "Assign PBI-102 to Alice." or "Change PBI-102 to In Progress."

Expected result:

- The orchestrator selects the matching MCP tool via schema discovery.
- The MCP server validates inputs and returns a success or failure result.
- The agent reports the action only after the MCP server confirms execution.

## Verification checklist

- UI remains passive and does not classify intent.
- No action executes without an MCP tool call.
- The toolset can be extended without modifying the routing logic.
- The answer is grounded in the correct source or a combination of both sources.
