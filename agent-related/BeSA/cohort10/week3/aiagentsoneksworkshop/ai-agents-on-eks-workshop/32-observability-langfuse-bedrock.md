# Observability using Langfuse (Integrated Track)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/200-observability-langfuse

## At a glance

- **Goal:** Trace the Bedrock-backed agent into the same Langfuse project, and see that the SDK emits identical spans whichever backend LiteLLM routes to.
- **Prerequisites:** The Agents using Strands with Bedrock lab

In this module, you'll wire Langfuse into the Bedrock-backed agent. Same Langfuse as the self-managed track. The Strands SDK emits the same OTel spans regardless of which backend LiteLLM routes to.

## Step 1: Reuse the Langfuse setup

```bash
echo "Langfuse UI: http://$(kubectl get ingress -n langfuse langfuse -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
```

Credentials and project are the same as the self-managed Observability using Langfuse lab. Traces from both tracks will land side by side in the AnyCompany Shop project.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/200-observability-langfuse/customer-agent
```

Same Langfuse wiring pattern as the self-managed Observability using Langfuse lab, just with a different `model_id` going through LiteLLM.

**agent.py — Langfuse + LiteLLM:**

```python
langfuse = get_client()
if langfuse.auth_check():
    print("Langfuse connected successfully")
else:
    print("WARNING: Langfuse authentication failed - traces will not be captured")

# ... OpenAIModel(base_url=LITELLM_BASE_URL, model_id="nova-lite") ...

langfuse.flush()
```

The integration follows the same three-line pattern used in the self-managed Observability lab: `get_client()`, `auth_check()`, and `flush()`. The API keys are sourced from the `agent-config` ConfigMap.

## Step 3: Deploy (image already built)

The `customer-agent:bedrock-langfuse` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/30-integrated/200-observability-langfuse/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent -n agents --timeout=120s
```

## Step 4: Chat and compare traces

Open the chat UI, pick **Customer Agent (Integrated GenAI)**, ask about an order.

- "Where is my order ORD-12345?"

In Langfuse, filter by model:

- **Self-managed runs:** model label `qwen2-5-3b-neuron`, latency dominated by inference on a 3B Neuron model
- **Integrated runs:** model label `nova-lite`, latency dictated by Bedrock

The trace structure is identical in both cases: agent loop → LLM call → tool call → LLM call. You also see LiteLLM's own spans in the same project because the proxy forwards them through its Langfuse callback. This separation lets you distinguish agent-side latency from proxy-side latency, a useful breakdown when you are tuning end-to-end response times.

## What you changed

- Kept the `[openai,otel]` Strands extras from the self-managed track (same dependency surface)
- `agent.py` reads Langfuse config from env (nothing hardcoded)
- Same `OpenAIModel` client, just a different `model_id`

## What's next

Milvus out, AgentCore Memory in. Session memory instead of vector search.
</content>
