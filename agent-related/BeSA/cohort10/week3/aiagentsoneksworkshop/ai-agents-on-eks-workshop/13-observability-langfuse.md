# Observability using Langfuse

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/300-observability-langfuse

## At a glance

- **Goal:** Trace every LLM call, tool invocation, and agent decision into Langfuse, then read one request end to end.
- **Prerequisites:** The Agents using Strands lab

In this module, you connect the agent to [Langfuse](https://langfuse.com/) to trace every LLM call, tool invocation, and agent decision. Langfuse is already running on your cluster, so you only need to plug in.

## What is Langfuse?

[Langfuse](https://langfuse.com/) is an open-source LLM observability platform. It ingests OpenTelemetry spans and renders them as structured traces: a hierarchical view of every LLM call, tool invocation, and agent decision in a single request. Think of it as Jaeger or Datadog APM, but purpose-built for LLM applications: it understands token counts, prompt/completion pairs, tool call boundaries, and cost attribution out of the box.

## Why observability matters for agents

Without traces, an agent is a black box. When a customer gets a wrong answer or the agent takes 10 seconds to respond, you want to know:

- How many LLM calls went into a single query?
- Did the agent call the right tool or hallucinate one that doesn't exist?
- Where's the latency: model, tool, or network?
- What exactly did you send the LLM?

Langfuse captures traces: a hierarchical view of everything the agent did.

## Architecture

1. Agent sends query to Qwen2.5-3B via LiteLLM → vLLM
2. Strands SDK emits OpenTelemetry spans for every LLM call and tool invocation
3. LiteLLM also forwards its own proxy-level spans into the same Langfuse project
4. Langfuse ingests OTel spans and renders them as structured traces
5. You explore traces, latencies, and token usage in the Langfuse UI

## How Langfuse integrates with Strands

With the `[otel]` extra, `strands-agents` automatically emits OTel spans for agent loops, LLM calls, and tool executions. Langfuse ingests them via its OTel-compatible endpoint, no manual instrumentation needed.

## Step 1: Verify Langfuse is running

```bash
kubectl get pods -n langfuse
```

All pods should be `Running`. The web pod may have 1-2 restarts, which is normal during initial database migration.

## Step 2: Access the Langfuse UI

```bash
echo "Langfuse UI: http://$(kubectl get ingress -n langfuse langfuse -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
```

| Field | Value |
|---|---|
| Email | admin@workshop.local |
| Password | workshop2025 |

The AnyCompany Shop project and API keys (`pk-lf-workshop` / `sk-lf-workshop`) are pre-provisioned.

## Step 3: Code walkthrough

```bash
cd ~/environment/modules/20-self-managed/300-observability-langfuse/customer-agent
```

The structure mirrors the Agents using Strands lab, with two additions: a Langfuse client initialized at the top of the file and a `flush()` call at the end to ensure all traces are exported. `tools.py` remains unchanged.

**agent.py — Langfuse wiring:**

```python
langfuse = get_client()
if langfuse.auth_check():
    print("Langfuse connected successfully")
else:
    print("WARNING: Langfuse authentication failed - traces will not be captured")

# ... agent construction ...

langfuse.flush()
```

- `get_client()` picks up `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` from env. All three live in `agent-config`.
- `auth_check()` turns silent OTel auth failures into loud ones.
- `flush()` after every `/chat` request pushes pending spans before the reply returns.

## Step 4: Deploy (image already built)

The `customer-agent:langfuse` image was pre-built and pushed to ECR during workshop provisioning, so you can deploy straight away:

```bash
cd ~/environment/modules/20-self-managed/300-observability-langfuse/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=120s
```

`:langfuse` is this module's tag. Apply picks up the image reference and rolls the Deployment on its own.

## Step 5: Chat and trace

Open the chat UI, pick **Customer Agent (Self-managed GenAI)**, ask about an order.

- "Where is my order ORD-12345?"

```
Trace: "Where is my order ORD-12345?"
├── Agent Loop
│   ├── LLM Call (qwen2-5-3b-neuron) — tool call decision
│   ├── Tool: lookup_order — ~2ms
│   └── LLM Call (qwen2-5-3b-neuron) — final response
└── Total: ~2s, 2 LLM calls, 1 tool call
```

Then flip to the Langfuse console and select **Tracing** from left navigation panel and select the trace.

## What you built

Every LLM call, tool invocation, and decision is captured. All of it runs on the cluster, no external services.

## What's next

The agent has no product knowledge yet, it can only look up orders. Next you'll wire up Milvus for the product catalog and FAQs.
</content>
