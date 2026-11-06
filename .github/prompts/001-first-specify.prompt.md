---
name: 001-first-specify
description: Define the functional requirements and acceptance scenarios for ProjectOps Agent.
agent: speckit.specify
---

Build a conversational AI assistant called **ProjectOps Agent** for managing and querying information about software projects.

The system must support two types of user requests:

1. Informational requests, where the user wants to obtain information.
2. Action requests, where the user wants the system to modify project state or perform an operation.

The system must autonomously determine which capabilities are required to satisfy each request.

### Informational capabilities

For informational requests, the system must use a centralized agent/graph pipeline.

The informational pipeline must be capable of retrieving information from two different sources:

- A document/text corpus using Retrieval-Augmented Generation (RAG).
- A Knowledge Graph containing structured entities and relationships.

The agent must be able to use either source independently when appropriate and combine results from both sources when necessary.

The Knowledge Graph should represent a small software-project domain containing entities such as:

- Projects
- People
- Work items
- Technologies

It should represent relationships such as:

- Person works on Project
- Work Item belongs to Project
- Person is assigned to Work Item
- Project uses Technology
- Work Item depends on Work Item

The document corpus should contain project documentation such as:

- project overview
- architecture documentation
- team documentation
- deployment documentation
- requirements

The system must be able to answer questions such as:

- "What are the deployment requirements for the Atlas project?"
- "Who is assigned to PBI-102?"
- "What technologies does the Atlas project use?"
- "Who owns the Atlas API migration and what does the migration documentation say about it?"

The last example must demonstrate that the agent can combine information obtained from the Knowledge Graph and RAG.

### Action capabilities

The system must support state-changing actions such as:

- assigning a work item to a person;
- changing the status of a work item;
- creating a work item.

All state-changing actions must be executed exclusively through an MCP Server.

The MCP Server must expose properly defined tools with schemas describing their parameters.

The agent must be able to select the appropriate MCP tool based on the user's request.

Example requests include:

- "Assign PBI-102 to Alice."
- "Change PBI-102 to In Progress."
- "Create a new PBI for upgrading Angular."

The agent must invoke the MCP Server for these operations.

The agent must never directly modify the underlying application state or database for an action.

### Autonomous routing

The system must not use keyword matching or hard-coded if/else logic to classify user requests.

The application must not contain routing logic such as checking whether a message contains words such as "assign", "create", "update", or similar keywords.

The LLM-powered agent must autonomously determine which available capabilities are required to satisfy the request.

The same agent must be capable of selecting informational retrieval tools and MCP action tools.

Natural-language variations of the same request must be handled without changing application routing logic.

### Separation of informational and action capabilities

The MCP Server must remain separate from the informational RAG and Knowledge Graph pipeline.

The MCP Server must not be used as an informational retrieval source.

RAG and Knowledge Graph capabilities must not directly execute state-changing actions.

The user interface must remain passive.

The user interface must only:

- accept user input;
- send requests to the agent;
- display responses.

The user interface must not classify requests, choose tools, invoke MCP actions directly, or decide whether RAG or Knowledge Graph retrieval is required.

### MCP extensibility

The system must support adding new MCP tools without modifying the agent's routing or decision-making logic.

For example, the initial MCP Server may expose:

- assign_work_item
- update_work_item_status

A new tool should subsequently be addable without changing the code responsible for deciding whether an action is required.

The agent should discover and select available tools based on their descriptions and schemas.

### Demonstration domain

Use a small fictional project-management domain called **Atlas**.

The example domain should contain:

- Project: Atlas
- People: Alice, Bob, David
- Technologies: .NET 10, Angular, PostgreSQL, Docker
- Work items: PBI-101, PBI-102, PBI-103

The exact data relationships can be defined during planning.

The purpose of this domain is to provide enough data to demonstrate RAG, Knowledge Graph retrieval, combined retrieval, and MCP actions without introducing unnecessary business complexity.

### Quality and acceptance expectations

The specification must include acceptance scenarios demonstrating:

1. An informational question answered through RAG.
2. An informational question answered through the Knowledge Graph.
3. A question requiring both RAG and Knowledge Graph information.
4. An action executed through an MCP tool.
5. A second action using another MCP tool.
6. Addition of a new MCP tool without modification to routing logic.
7. Confirmation that the UI does not perform routing.
8. Confirmation that keyword-based intent routing is not used.
9. Confirmation that informational capabilities cannot directly execute actions.
10. Confirmation that actions cannot bypass the MCP Server.

The specification should focus on system behavior, requirements, constraints, and acceptance criteria.

Do not prematurely prescribe detailed implementation code or project structure. Implementation technologies and architecture details that are not explicitly required above should be determined during the planning phase.
