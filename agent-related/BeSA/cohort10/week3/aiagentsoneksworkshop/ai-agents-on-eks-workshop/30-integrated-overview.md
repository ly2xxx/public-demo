# Integrated GenAI Strategy

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure

## Deploying Agents on Integrated EKS Infrastructure

In this section, you keep EKS for orchestration and replace self-hosted components with AWS managed services:

- **Amazon Bedrock** for inference, routed through the shared LiteLLM proxy from the self-managed track. Your agent code stays identical; only the `model_id` changes.
- **AgentCore Memory** for session history.
- **AgentCore sandboxes** for isolated tool execution.

## Architecture Overview

```
EKS Cluster (Auto Mode)
├── agents namespace
│   └── Strands Agent (ServiceAccount: agent)
│       │  OpenAIModel(base_url=LITELLM_BASE_URL, model_id="nova-lite")
│       ▼
├── litellm namespace
│   └── LiteLLM proxy (Pod Identity → Bedrock IAM)
│       │
│       ▼
│   Amazon Bedrock (LLM inference via LiteLLM route)
│   AgentCore Memory (session history, accessed directly via Pod Identity)
│   AgentCore Browser (sandboxed web actions)
│   AgentCore Code Interpreter (sandboxed code execution)
└── langfuse namespace
    └── Langfuse (observability, reused from self-managed track)
```

## Modules

- **Agents using Strands with Bedrock:** flip `model_id` from `qwen2-5-3b-neuron` to `nova-lite`. LiteLLM handles the rest.
- **Observability using Langfuse:** same Langfuse, now tracing Bedrock via LiteLLM
- **Memory management using AgentCore Memory:** session memory via `bedrock-agentcore`
- **Managed sandboxed tools (Browser + Code Interpreter):** offload risky work
- **Multi-agent interaction (A2A):** multi-agent orchestration, managed edition
- **Evaluation with AgentCore:** score every conversation with AgentCore Evaluations (built-in + custom evaluators)
</content>
