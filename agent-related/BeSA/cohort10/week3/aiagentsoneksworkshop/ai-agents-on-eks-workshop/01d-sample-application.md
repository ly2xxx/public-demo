# Sample Application

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/10-introduction/350-sample-application

Throughout this workshop, you'll build and evolve a customer service agent for **AnyCompany Shop**, a fictional online retail store that sells electronics and accessories.

## The scenario

AnyCompany Shop needs an AI-powered agent that can handle common customer inquiries without routing to a human. Customers chat with the agent through a web UI and expect it to:

- Look up order status, tracking numbers, and delivery estimates
- Answer product questions using the store's catalog
- Check inventory availability
- Process return requests
- Do light computation (e.g., "total up my two orders")

You'll start with a single agent that can only look up orders, then layer on capabilities module by module until you have a multi-agent system with observability, memory, tool access, and sandboxed execution.

## Data model

The agent works with three data sources that evolve as you progress through the labs:

**Orders:** three sample orders used across every lab:

| Order ID | Customer | Item | Status |
|---|---|---|---|
| ORD-12345 | Jane Doe | Laptop Pro 15 ($1,299.99) | Shipped |
| ORD-67890 | John Smith | Wireless Mouse + 2× USB-C Hub ($129.97) | Delivered |
| ORD-11111 | Alice Johnson | Noise Cancelling Headphones ($249.99) | Processing |

These start as a hardcoded dict in `tools.py`, then move to an MCP server in the Agent Tool Access (MCP) lab.

**Product catalog:** ~13 products and FAQs embedded as vectors in Milvus. Added in the RAG with Milvus lab for RAG-powered product answers.

**Inventory:** stock levels for 10 products, served via the MCP server's `check_inventory` tool.

## Agent capabilities by lab

The agent gains one new capability per module. Each row builds on the previous, and later labs retain everything from earlier ones:

| Lab | New capability | How it works |
|---|---|---|
| Strands Agents | Core agent loop + `lookup_order` | LLM decides when to call the tool based on the query |
| Observability (Langfuse) | Tracing | Every LLM call, tool invocation, and decision is captured as an OTel span |
| Memory (Milvus / AgentCore) | Product knowledge or session memory | Self-managed: vector search over the catalog. Integrated: conversation history across turns |
| Tool Access (MCP / AgentCore) | Dynamic tools + sandboxed execution | MCP server for order/inventory tools. Integrated track adds Code Interpreter + Browser |
| Multi-Agent (A2A) | Specialist routing | Orchestrator dispatches to Order Agent and Product/Sandbox Agent over A2A |

## The chat UI

A Chainlit-based web UI is pre-deployed on the cluster. It includes a profile dropdown with four entries, one for each combination of track and mode (single-agent or multi-agent). All profiles send requests to the same `/chat` endpoint; the only difference is which in-cluster Service they target.

To open it in your browser, run:

```bash
echo $CHAT_UI_URL
```

**Note:** Most profiles won't work yet because their agent Services haven't been deployed. They will become available as you complete each lab. Keep this tab open and use it throughout every lab.
</content>
