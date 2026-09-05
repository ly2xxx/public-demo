# Agents using Strands

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/200-strands-agents

## At a glance

- **Goal:** Build and deploy the AnyCompany Shop customer service agent with the Strands Agents SDK, backed by the in-cluster Qwen2.5-3B model.
- **Prerequisites:** The Model Plane lab

In this module, you'll build and deploy an AI-powered Customer Service Agent for a fictional online retail store called AnyCompany Shop using the [Strands Agents SDK](https://github.com/strands-agents/sdk-python). The agent talks to the Qwen2.5-3B model running in your cluster and helps customers with orders, product questions, and returns.

## Architecture

1. Customer query → Strands Agent
2. Agent sends prompt → LiteLLM → Qwen2.5-3B via vLLM
3. Model decides to call `lookup_order`
4. Agent executes tool, returns result to model
5. Model generates final response → Customer

## What is Strands SDK?

An open-source Python SDK for building agents. The LLM decides which tools to call and in what order. Key concepts:

- **Agent:** the main loop that sends messages to the LLM and executes tool calls
- **Model:** any OpenAI-compatible endpoint (here, LiteLLM routing to vLLM)
- **Tools:** Python functions decorated with `@tool` that the agent can invoke
- **System prompt:** instructions that shape the agent's behavior

## Step 1: Code walkthrough

The full source is available under `~/environment/modules/20-self-managed/200-strands-agents/customer-agent`.

```bash
cd ~/environment/modules/20-self-managed/200-strands-agents/customer-agent
```

The project consists of six files: `agent.py`, `tools.py`, `server.py`, `Dockerfile`, `requirements.txt`, and `k8s.yaml`. The first two are the core teaching files — they contain the agent logic and tool definitions. The remaining files are infrastructure: `server.py` is a thin FastAPI wrapper that exposes the agent over HTTP for the chat UI, `Dockerfile` and `requirements.txt` handle containerization and dependencies, and `k8s.yaml` defines the Kubernetes deployment.

**agent.py — the model client:**

```python
model = OpenAIModel(
    client_args={
        "base_url": litellm_base_url,
        "api_key": os.environ.get("LITELLM_API_KEY", "not-needed"),
    },
    model_id="qwen2-5-3b-neuron",
    params={"max_tokens": 1024, "temperature": 0.3},
)
```

- `model_id="qwen2-5-3b-neuron"`: LiteLLM resolves this to the vLLM Service. Flip to `"nova-lite"` and you're on Bedrock with zero other code changes
- Qwen3's extended thinking is disabled at the LiteLLM proxy level (`extra_body.chat_template_kwargs.enable_thinking = false` in the model config), so agents don't need to handle it
- `LITELLM_BASE_URL` comes from the `agent-config` ConfigMap Terraform provisioned

## Step 2: Build and push to ECR

We already created the Amazon ECR repo for the customer-agent. Build and push in one shot:

```bash
cd ~/environment/modules/20-self-managed/200-strands-agents/customer-agent
IMG=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/customer-agent:strands
docker build --push -t $IMG .
```

`:strands` is the module-specific tag. Every lab uses a different tag name so `kubectl describe pod` tells you exactly which module's code is running, and a fresh `kubectl apply` is enough to roll the Deployment (spec changed, no rollout restart needed).

This is the only lab where you build and push the image by hand, so you can see the full source → container image → ECR → EKS loop end-to-end. For every later lab we pre-built and pushed the images to ECR, so you can go straight to deploy. Rebuild and push any time you want to ship your own changes.

## Step 3: Deploy to EKS

`k8s.yaml` is a Deployment + ClusterIP Service on port 8080. `envFrom` mounts the `agent-config` ConfigMap, so `LITELLM_BASE_URL` lands automatically.

```bash
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=120s
```

## Step 4: Chat with it

Open the chat UI. Pick **Customer Agent (Self-managed GenAI)** from the profile list, then try:

- "Hi, I ordered a laptop last week and it still hasn't arrived. My order ID is ORD-12345. Can you help?"
- "I want to return the headphones I bought. Order ORD-11111."
- "Can you check on order ORD-99999?"

The last one tests the "order doesn't exist" path — good agents fail gracefully.

## What you built

- An agent connected to the self-hosted Qwen2.5-3B model via LiteLLM (a universal OpenAI-compatible proxy sitting in front of vLLM)
- A Strands agent loop handling customer service conversations
- A `lookup_order` tool the model calls to fetch order info
- A long-running HTTP service on EKS the chat UI talks to

## What's missing

- No observability: the agent is a black box right now → Langfuse module
- No product knowledge: can only look up orders → Milvus module
- Mock data only: hardcoded orders → MCP module
- Single agent: juggling too many hats → A2A module

Next up: observability, trace every LLM call and tool invocation.
</content>
