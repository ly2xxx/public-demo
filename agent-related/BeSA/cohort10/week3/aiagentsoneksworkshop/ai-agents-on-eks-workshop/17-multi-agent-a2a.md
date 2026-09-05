# Multi-Agent Interaction (A2A)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/700-multi-agent-a2a

## At a glance

- **Goal:** Split the single agent into specialists that talk over the A2A protocol, with an orchestrator routing each request.
- **Prerequisites:** The Agent Tool Access (MCP) lab

In this module, you'll split the single agent into specialists talking to each other via the [Agent-to-Agent (A2A) protocol](https://a2aproject.github.io/A2A/). An orchestrator decides who does what.

## Why multi-agent?

A single agent can handle simple workflows, but complexity exposes its limits. As the system prompt grows, the LLM begins to confuse similar tools, and updating one capability requires changes to the entire agent. Agent-to-Agent (A2A) communication solves this by assigning each agent a single responsibility: one prompt, one job.

## Architecture

- **Order Agent:** lookups and returns, via the MCP server from the Agent Tool Access (MCP) lab
- **Product Agent:** product/FAQ search, via Milvus
- **Orchestrator:** routes queries to the right specialist over A2A

## Step 1: Code walkthrough

```bash
cd ~/environment/modules/20-self-managed/700-multi-agent-a2a/a2a-agents
```

This module defines three agents, each in its own file. All three run as long-lived HTTP servers. The specialist agents accept requests through A2A JSON-RPC, while the orchestrator agent exposes a `/chat` endpoint that the UI calls directly.

**order_agent.py — A2A server shape:**

```python
class OrderAgentExecutor(AgentExecutor):
    def __init__(self):
        self.mcp_client = mcp_client
        self.mcp_client.__enter__()
        self.agent = Agent(
            model=model, system_prompt="You handle order inquiries...",
            tools=self.mcp_client.list_tools_sync(),
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        reply = str(self.agent(query))
        await event_queue.enqueue_event(new_agent_text_message(reply))

agent_card = AgentCard(
    name="Order Agent",
    url="http://order-agent.default.svc.cluster.local:8081",
    capabilities=AgentCapabilities(streaming=False),
    default_input_modes=["text"], default_output_modes=["text"],
    skills=[AgentSkill(id="orders", name="Order Management", ..., tags=["orders"])],
    version="1.0.0", description="Handles order status lookups and return processing",
)

app = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=DefaultRequestHandler(OrderAgentExecutor(), InMemoryTaskStore()),
)
```

The `a2a-sdk` relies on three key components:

- **`AgentExecutor.execute(context, event_queue)`:** Retrieves the user's query from `context.get_user_input()` and sends the agent's reply through `event_queue.enqueue_event(new_agent_text_message(...))`. This is the core execution loop for handling requests.
- **`AgentCard`:** Publishes agent metadata at `/.well-known/agent.json`, which other agents and clients use for discovery.
- **`A2AStarletteApplication`:** Wraps the agent as an ASGI application that speaks the A2A JSON-RPC wire protocol.

## Step 2: Deploy specialists + orchestrator (images already built)

The `order-agent:v1`, `product-agent:v1`, and `orchestrator-agent:v1` images were pre-built and pushed to ECR during provisioning, so deploy them directly:

```bash
cd ~/environment/modules/20-self-managed/700-multi-agent-a2a/a2a-agents
envsubst < k8s-specialists.yaml | kubectl apply -f -
envsubst < k8s-orchestrator.yaml | kubectl apply -f -

kubectl rollout status deployment/order-agent --timeout=120s
kubectl rollout status deployment/product-agent --timeout=120s
kubectl rollout status deployment/orchestrator-agent --timeout=120s
```

## Step 3: Chat

Open the chat UI, pick **Multi-Agent (Self-managed GenAI)**, and alternate between branches in the same conversation:

- "Where is my order ORD-12345?" → Routes to the Order Agent.
- "Do you have any good monitors for working from home?" → Routes to the Product Agent.

In Langfuse you'll see the orchestrator's trace with `ask_order_agent` (or `ask_product_agent`) as a tool call. That's the A2A dispatch. The specialist's work (e.g., `lookup_order` via MCP, or `search_products` via Milvus) shows up as a separate top-level trace because the JSON-RPC hop crosses a process boundary.

## What you built

A multi-agent system where:

- Orchestrator routes based on query semantics
- Order Agent handles orders/returns via MCP
- Product Agent does RAG against Milvus
- All agents share the same model plane (LiteLLM → vLLM)
- Every hop is traced in Langfuse, including LiteLLM's own proxy spans

## Self-managed track summary

Next up: put this agent under scrutiny. You'll add automated quality scoring with LLM-as-a-Judge in Langfuse, using `claude-sonnet-4-5` to grade every conversation. After that, connect the agent to a knowledge graph in the Knowledge Graph with Neo4j lab, where relationships — not just similarity — drive retrieval.
</content>
