# Agent Tool Access (MCP)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/600-agent-tools-mcp

## At a glance

- **Goal:** Move the agent's tools onto the network: build an MCP server with order and inventory tools, deploy it on EKS, and have the agent discover it at runtime.
- **Prerequisites:** The Agents using Strands lab

In this module, you'll build an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server with order and inventory tools, deploy it on EKS, and connect the agent to it. Goodbye hardcoded mock.

## What is MCP?

MCP is an open protocol for how agents discover and call tools. Instead of hardcoding tools in the agent, the agent connects to a server that advertises them. Tool logic is decoupled from agent logic. You can reuse tools across agents and update tools without redeploying.

## Step 1: Build the MCP server

```bash
cd ~/environment/modules/20-self-managed/600-agent-tools-mcp/mcp-server
```

**server.py — the tools:**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AnyCompany Tools")

@mcp.tool()
def lookup_order(order_id: str) -> dict:
    """Look up order status, tracking, and details by order ID."""
    ...

@mcp.tool()
def check_inventory(product_name: str) -> dict:
    """Check stock availability for a product."""
    ...
```

- The `@mcp.tool()` decorator works the same way as `@tool` in Strands Agents. You write a plain Python function, and FastMCP automatically generates the tool schema from the function signature and docstring.
- The server defines three tools, each backed by its own independent mock dataset.
- At the bottom of the file, `mcp.streamable_http_app()` returns an ASGI application that uvicorn serves directly.

## Step 2: Deploy the MCP server (image already built)

The `mcp-server:v1` image was pre-built and pushed to ECR during provisioning, so deploy it directly:

```bash
cd ~/environment/modules/20-self-managed/600-agent-tools-mcp/mcp-server
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/mcp-server --timeout=60s
```

## Step 3: Connect the agent to MCP

```bash
cd ~/environment/modules/20-self-managed/600-agent-tools-mcp/customer-agent
```

The `tools.py` file is no longer needed because the mock data now lives in the MCP server. At startup, the agent retrieves the available tool list from the MCP server and passes it directly to `Agent(tools=...)`.

**agent.py — MCP client + tool discovery:**

```python
mcp_client = MCPClient(lambda: streamablehttp_client(mcp_server_url))
mcp_client.__enter__()

mcp_tools = mcp_client.list_tools_sync()
print(f"Discovered {len(mcp_tools)} MCP tools: {[t.tool_name for t in mcp_tools]}")

agent = Agent(model=model, system_prompt=SYSTEM_PROMPT,
              tools=[search_products, *mcp_tools])
```

- `list_tools_sync()` pulls the tool schema from the server at startup. The agent didn't know these tools existed until this line ran.
- The client is kept open for the whole process lifetime. Long-running HTTP server = connection stays up across requests; a fresh connection per request would be painful.

## Step 4: Redeploy the agent (image already built)

The `customer-agent:mcp` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/20-self-managed/600-agent-tools-mcp/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=180s
```

## Step 5: Chat

Open the chat UI, pick **Customer Agent (Self-managed GenAI)**, and try a flow that uses two MCP tools in one conversation:

- "I want to return the headphones from order ORD-11111"

The agent should call `lookup_order`, see the status is `processing`, and refuse to initiate a return, all visible in Langfuse.

## What you built

- An MCP server running on EKS that exposes three tools: `lookup_order`, `check_inventory`, and `initiate_return`
- An agent that discovers available tools from the MCP server dynamically at startup, rather than relying on a hardcoded list
- A clean separation of concerns: the local mock tool file is removed, and all tool logic now resides in the MCP server

## What's next

One agent doing everything. Next you'll split it into specialists coordinating over A2A.
</content>
