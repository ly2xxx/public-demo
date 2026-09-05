# Multi-Agent Interaction (A2A) (Integrated Track)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/500-multi-agent-a2a

## At a glance

- **Goal:** Split the Bedrock agent into A2A specialists, each riding on Bedrock through LiteLLM and AgentCore.
- **Prerequisites:** The Managed Capabilities lab

In this module, you'll split the single agent into specialists talking over A2A. This follows the same shape as the self-managed Multi-Agent Interaction (A2A) module, but each specialist rides on Bedrock via LiteLLM + AgentCore.

## What's different from Self-managed GenAI

MCP stays. Domain-specific tools don't belong in AgentCore. Everything else swaps.

## Step 1: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/500-multi-agent-a2a/a2a-integrated
```

This module defines three agents, each in its own Python file. All three run as long-lived HTTP services. The specialist agents accept requests through A2A JSON-RPC, while the orchestrator exposes a `/chat` endpoint that the UI calls directly.

Files: `order_agent.py`, `sandbox_agent.py`, `orchestrator.py` (the glue), `server.py` (HTTP wrapper).

Near-identical to the self-managed Order Agent: same A2A shape, same MCP client, same `OpenAIModel` client. Only the `model_id` and namespace change:

```python
# All that changes vs the self-managed Multi-Agent A2A lab:
from strands.models.openai import OpenAIModel
model = OpenAIModel(
    client_args={"base_url": os.environ["LITELLM_BASE_URL"], "api_key": os.environ.get("LITELLM_API_KEY", "not-needed")},
    model_id=os.environ.get("MODEL_ID", "nova-lite"),  # was "qwen2-5-3b-neuron"
    params={"max_tokens": 1024, "temperature": 0.3},
)
# ... and the AgentCard.url lives in the `agents` namespace.
```

No additional changes are required. The MCP tools, `A2AStarletteApplication`, and executor pattern all remain identical. LiteLLM handles the Bedrock translation transparently, so the agent code stays the same regardless of the underlying model provider.

## Step 2: Images already built

The `order-agent:bedrock`, `product-agent:bedrock`, and `orchestrator-agent:bedrock` images were pre-built and pushed to ECR during provisioning. Note the sandbox image is pushed to the `product-agent` repo (reused from the self-managed track).

## Step 3: Deploy specialists + orchestrator

The `k8s-specialists.yaml` manifest also deploys the MCP server into the `agents` namespace, making this lab fully self-contained. You do not need the MCP server from the self-managed Agent Tool Access (MCP) lab to be running. The order agent connects to the MCP server at `mcp-server.agents.svc.cluster.local:8080/mcp`, configured through an environment variable.

```bash
envsubst < k8s-specialists.yaml | kubectl apply -f -
envsubst < k8s-orchestrator.yaml | kubectl apply -f -

kubectl rollout status deployment/mcp-server -n agents --timeout=120s
kubectl rollout status deployment/order-agent -n agents --timeout=120s
kubectl rollout status deployment/sandbox-agent -n agents --timeout=120s
kubectl rollout status deployment/orchestrator-agent -n agents --timeout=120s
```

All three agents use `serviceAccountName: agent`, inheriting the Pod Identity binding for AgentCore. Model calls go out through LiteLLM; the proxy holds the Bedrock IAM role.

## Step 4: Chat across turns

Open the chat UI, pick **Multi-Agent (Integrated GenAI)**. Run two turns in the same browser tab:

Turn 1 (establishes context across specialists):
- "I want to total up what I spent on orders ORD-12345 and ORD-67890."

You'll see the orchestrator fan out: `ask_order_agent` for each order, then `ask_sandbox_agent` to run the arithmetic.

Turn 2 (same tab, no order IDs):
- "Has either of them shipped yet?"

The orchestrator should route correctly by pulling context from the prior turn's AgentCore Memory events.

## Step 5: Check Langfuse

The orchestrator trace now nests:

```
Orchestrator (LiteLLM → Nova)
├── ask_order_agent (A2A → order-agent)
│   └── Order Agent (LiteLLM → Nova)
│       ├── lookup_order (MCP)
│       └── LLM response
├── ask_sandbox_agent (A2A → sandbox-agent)
│   └── Sandbox Agent (LiteLLM → Nova)
│       ├── run_python (AgentCore Code Interpreter)
│       └── LLM response
└── Final LLM response
```

Compare against a trace from the self-managed Multi-Agent A2A lab: same shape, same spans, just different `model_id` labels. LiteLLM also emits its own spans so you can see proxy-side latency separately.

## Track summary

Neither approach is universally better. Each capability is an independent choice. Use EKS as your agent runtime and select managed or self-hosted components based on your team's operational requirements, compliance needs, and scaling priorities.

## What's next

Put the agent under scrutiny. Next you'll add automated quality scoring with AgentCore Evaluations, scoring every conversation with built-in and custom LLM-as-a-Judge evaluators.
</content>
