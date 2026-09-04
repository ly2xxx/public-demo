are you able to access current page and extract to .md?

Great, can you extract the rest of the pages put them in top level folder then create a top level .md index file?

# Model Plane: vLLM + LiteLLM on EKS

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/100-vllm-on-eks

## At a glance

- **Goal:** Understand the shared model plane every agent in the workshop calls: Qwen2.5-3B on AWS Inferentia behind vLLM, with LiteLLM as the single proxy in front of it and Bedrock.
- **Prerequisites:** None. This is the first lab of the track.

In this module, you'll see how every agent in the workshop hits a single model endpoint, regardless of track. Qwen2.5-3B runs on AWS Inferentia with vLLM, and LiteLLM sits in front of it (and in front of Bedrock) as the one proxy that every agent talks to. Nothing for you to install here. Both are already running.

## Why two components, not one?

vLLM serves the self-hosted model (Qwen2.5-3B on Inferentia). LiteLLM is a thin OpenAI-compatible proxy that routes requests by model name:

- `model: qwen2-5-3b-neuron` → vLLM (self-managed track)
- `model: nova-lite` → Amazon Bedrock (integrated track)
- `model: claude-sonnet-4-5` → Amazon Bedrock (the stronger model used as the judge in the LLM-as-a-Judge lab)

Because every agent calls LiteLLM instead of vLLM or Bedrock directly, switching tracks becomes a one-line change in the agent: flip `model_id` from `"qwen2-5-3b-neuron"` to `"nova-lite"`. Same `OpenAIModel` client, same base URL, same code path. The proxy handles the rest, including AWS IAM for Bedrock via Pod Identity on the LiteLLM pod. Adding a model like the `claude-sonnet-4-5` judge is just another route entry in the same proxy config, no new infrastructure.

**What is vLLM?**
[vLLM](https://github.com/vllm-project/vllm) is a high-throughput LLM serving engine with continuous batching, paged attention, and a standard chat-completions–style API. It runs on AWS Neuron SDK for Inferentia and Trainium.

**What is AWS Inferentia?**
[AWS Inferentia](https://aws.amazon.com/machine-learning/inferentia/) is a purpose-built ML accelerator for high-performance, low-cost inference. Inferentia2 (inf2) instances have up to 12 NeuronCores and 384 GB of HBM.

**What is LiteLLM?**
[LiteLLM](https://www.litellm.ai/) speaks the OpenAI chat-completions format on the front and translates to any of 100+ backends on the back (vLLM, Bedrock, OpenAI, Azure, and so on). In this workshop we use it as the model plane every agent talks to. It also forwards its own spans into Langfuse, so you'll see proxy-level traces alongside the per-agent ones later.

## Architecture

```
Agent pod (any track)
OpenAIModel(base_url=LITELLM_BASE_URL)
        │
        ▼
┌─── LiteLLM Proxy (litellm namespace) ──────────┐
│  qwen2-5-3b-neuron → vLLM                      │
│  nova-lite          → Bedrock (Pod Identity)   │
│  claude-sonnet-4-5  → Bedrock (Pod Identity)   │
└────┬───────────────────────────────────────┬────┘
     ▼                                       ▼
vLLM on Inferentia                    Amazon Bedrock
(Qwen2.5-3B)                          nova-lite: us.amazon.nova-2-lite-v1:0
                                       claude-sonnet-4-5: us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

## What was pre-deployed during workshop setup

### Verify the deployment

Both namespaces should be `Running`:

```bash
kubectl get pods -n vllm -l app=qwen2-5-3b-neuron
kubectl get pods -n litellm
```

If the LiteLLM pods are not in `Running` state, restart the deployment:

```bash
kubectl rollout restart deploy/litellm -n litellm && kubectl rollout status deploy/litellm -n litellm --timeout=120s
```

Check the LiteLLM model routing table loaded into the proxy:

```bash
kubectl logs deploy/litellm -n litellm | grep -iE -B2 -A3 "qwen|nova-lite|claude-sonnet"
```

Expected output:

```
Initialized Success Callbacks - ['langfuse']
LiteLLM: Proxy initialized with Config, Set models:
    qwen2-5-3b-neuron
    nova-lite
    claude-sonnet-4-5
INFO:     10.0.6.254:51626 - "GET /health/readiness HTTP/1.1" 200 OK
INFO:     10.0.6.254:51630 - "GET /health/readiness HTTP/1.1" 200 OK
```

You should see all three routes (`qwen2-5-3b-neuron`, `nova-lite`, `claude-sonnet-4-5`) in the startup logs.

> **Note:** The "Set models" block is printed once at startup. On a pod that has been running for a while it gets buried under request logs — or ages out of the log buffer entirely — so an empty grep result here does not mean the routes are missing. The curl tests below (and the Models + Endpoints panel in the admin UI) are the definitive confirmation of routing. To force a fresh startup block, restart the proxy: `kubectl rollout restart deploy/litellm -n litellm`.

### Test inference via LiteLLM

Grab the ingress URL and the generated master key. You'll use both for the curl tests and again for the admin UI below:

```bash
LITELLM_URL="http://$(kubectl get ingress -n litellm litellm -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
LITELLM_KEY=$(kubectl get cm agent-config -n default -o jsonpath='{.data.LITELLM_API_KEY}')
echo "URL: $LITELLM_URL"
echo "Key: $LITELLM_KEY"
```

If `$LITELLM_URL` prints an empty string, the ALB is still provisioning. Give it 60 seconds and re-run. The master key is a random per-deployment value Terraform generates and writes into the `agent-config` ConfigMap.

Hit the proxy with the self-managed model name. The request goes to vLLM on Inferentia:

```bash
curl -s $LITELLM_URL/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2-5-3b-neuron",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 100
  }'
```

Now flip the model name. The proxy routes this one to Bedrock instead. The agent code wouldn't know or care:

```bash
curl -s $LITELLM_URL/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nova-lite",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 100
  }'
```

One more — the judge route. Same endpoint again, this time routed to the stronger Claude model on Bedrock that the LLM-as-a-Judge lab uses to score the agent:

```bash
curl -s $LITELLM_URL/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "max_tokens": 100
  }'
```

Same endpoint, same payload shape, different backend. That's the whole point.

### Explore the LiteLLM admin UI

LiteLLM also ships a small admin UI at `/ui`. The same ALB serves it. Open it in your browser and enter the LiteLLM key:

```bash
echo "$LITELLM_URL/ui"
echo "$LITELLM_KEY"
```

Log in with username `admin` and the `$LITELLM_KEY` value you printed above as the password. What's clickable:

- **Models + Endpoints:** the three routes from the config file, same list you hit with curl
- **Playground:** a chat box that sends through the proxy. Flip the model dropdown to see Qwen vs Nova vs the Claude judge side by side without touching any Python
- **Logs:** every request the proxy has handled, with latency and cached-vs-upstream status. Useful for spotting agents that keep asking the same thing
- **Virtual Keys:** scoped API keys with budgets

## Reference

### Key configuration (vLLM)

| Parameter            | Value                                      | Description                                                      |
| -------------------- | ------------------------------------------ | ---------------------------------------------------------------- |
| Model                | `Qwen/Qwen2.5-3B-Instruct`               | 3B parameter model, pre-compiled for Neuron using optimum-neuron |
| Instance             | `inf2.xlarge`                            | 1 Neuron device, 2 NeuronCores                                   |
| Image                | `vllm-neuron: qwen2.5-3b-optimum-neuron` | Pre-compiled model baked into Docker image                       |
| tensor-parallel-size | 2                                          | Distributes model across 2 NeuronCores                           |
| max-model-len        | 8192                                       | Maximum context length                                           |
| max-num-seqs         | 2                                          | Maximum concurrent sequences                                     |

### Key configuration (LiteLLM)

| Setting                  | Value                                                       | Description                                                                                   |
| ------------------------ | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Aliases                  | `qwen2-5-3b-neuron`, `nova-lite`, `claude-sonnet-4-5` | Names agents use in`model_id`                                                               |
| vLLM upstream            | `http://qwen2-5-3b-neuron.vllm.svc.cluster.local:8000/v1` | In-cluster Service                                                                            |
| Bedrock upstream (agent) | `bedrock/us.amazon.nova-2-lite-v1:0`                      | Region defaulted from the pod's AWS env                                                       |
| Bedrock upstream (judge) | `bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0`    | Stronger model for LLM-as-a-Judge scoring                                                     |
| Callbacks                | `langfuse`                                                | Forwards LiteLLM's own spans to the workshop Langfuse project                                 |
| Master key               | `$LITELLM_KEY`                                            | Generated by Terraform, surfaced through the`agent-config` ConfigMap as `LITELLM_API_KEY` |

### How a request flows end to end

1. **Agent:** `OpenAIModel(base_url=LITELLM_BASE_URL, model_id="qwen2-5-3b-neuron")`. Exactly the same Python for every lab in this track.
2. **LiteLLM:** reads the `model` field, looks up the route in its config, calls the upstream
3. **vLLM:** loads the pre-compiled Qwen2.5-3B onto NeuronCores (~2–3 minutes at cold start) and serves OpenAI-format responses
4. **Bedrock (other track):** LiteLLM uses the AWS credentials from Pod Identity, calls Converse, translates the response back to OpenAI format
5. **Langfuse:** traces from both the agent and the proxy land in the same project, so you can see where time is spent
