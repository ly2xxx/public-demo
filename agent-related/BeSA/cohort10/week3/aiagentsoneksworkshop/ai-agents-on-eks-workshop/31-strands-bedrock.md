# Agents using Strands with Bedrock

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/100-strands-bedrock

## At a glance

- **Goal:** Move the same agent onto Amazon Bedrock by changing one value, `model_id`, and confirm nothing else has to change.
- **Prerequisites:** The self-managed Agents using Strands lab

In this module, you migrate the customer service agent from the self-managed track to Amazon Bedrock. The agent code, SDK, and HTTP endpoint remain identical. The only change is the `model_id` value.

## One-line swap

Both tracks talk to the same LiteLLM proxy over the OpenAI wire format. LiteLLM routes by model name:

| model_id | LiteLLM sends to | Track |
|---|---|---|
| `qwen2-5-3b-neuron` | vLLM on Inferentia | Self-managed |
| `nova-lite` | Amazon Bedrock (Nova 2 Lite) | This module |

No additional changes are required. The agent does not need a new SDK, client library, or authentication configuration. LiteLLM assumes the Bedrock IAM role through Pod Identity, so the agent pods remain credential-free.

## Step 1: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/100-strands-bedrock/customer-agent
```

The `tools.py` is unchanged from the self-managed Agents using Strands lab. Only the `model_id` value changes.

**agent.py — OpenAIModel + LiteLLM:**

```python
from strands.models.openai import OpenAIModel

model = OpenAIModel(
    client_args={
        "base_url": os.environ["LITELLM_BASE_URL"],
        "api_key": os.environ.get("LITELLM_API_KEY", "not-needed"),
    },
    model_id=os.environ.get("MODEL_ID", "nova-lite"),
    params={"max_tokens": 1024, "temperature": 0.3},
)
```

- `OpenAIModel`: same client class the self-managed agent uses
- `model_id="nova-lite"`: LiteLLM alias that resolves to `bedrock/us.amazon.nova-2-lite-v1:0`
- `LITELLM_BASE_URL` comes from the `agent-config` ConfigMap in the `agents` namespace
- No boto3, no IAM wiring in the agent. Bedrock creds live on the LiteLLM pod.

## Step 2: Deploy (image already built)

The `customer-agent:bedrock` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/30-integrated/100-strands-bedrock/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent -n agents --timeout=120s
```

## Step 3: Chat

Open the chat UI, pick **Customer Agent (Integrated GenAI)**, and try:

Deployment and model access may take a minute. If the first request times out, wait briefly and retry.

- "Hi, I ordered a laptop last week and it still hasn't arrived. My order ID is ORD-12345. Can you help?"
- "I want to return the headphones I bought. Order ORD-11111."

Same questions as the self-managed agent, different model under the hood. If you port-forward LiteLLM and watch its logs, you'll see the request go out to Bedrock.

## What's next

Reconnect Langfuse and confirm the trace shape is the same regardless of backend. Observability doesn't care where the tokens came from.
</content>
