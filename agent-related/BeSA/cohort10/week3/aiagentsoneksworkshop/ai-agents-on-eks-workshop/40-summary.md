# Summary

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/40-summary

Nice work. You built a customer service agent, then rebuilt it twice: once on pure open-source, once mixing in AWS managed capabilities.

## What you built

**Shared model plane:**

- A single LiteLLM proxy in front of every backend. Agents in both tracks call one OpenAI-compatible endpoint, and backend swaps happen as a one-line `model_id` change.
- Pod Identity on the LiteLLM pod holds Bedrock IAM, so agents stay credential-free for model calls

**Self-managed GenAI infrastructure:**

- Qwen2.5-3B served on AWS Inferentia chips via vLLM, fronted by LiteLLM
- Strands agents wired to the shared model plane with `OpenAIModel`
- Langfuse tracing every LLM call and tool invocation (plus LiteLLM's own proxy spans)
- Product knowledge via Milvus (vector RAG)
- Business tools over an MCP server on EKS
- Specialists coordinating over A2A

**Integrated GenAI infrastructure:**

- vLLM → Amazon Bedrock (a one-line `model_id` swap, and LiteLLM does the rest)
- Session memory via AgentCore Memory
- Sandboxed work offloaded to AgentCore Code Interpreter + AgentCore Browser
- Langfuse, MCP, A2A, and the agent code path unchanged. Those layers don't care about the backend.
- Pod-level AWS auth via EKS Pod Identity (no static creds in the cluster)

## The point

Each piece is an independent decision. You don't have to pick "EKS + OSS" or "all-managed" as a package. Pick per capability, keep orchestration on EKS, and let the model plane (LiteLLM) absorb the backend choice so the agent never has to.

## Clean up

Running at an AWS event? Resources are cleaned up automatically.

## Next steps

- [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
- [LiteLLM](https://www.litellm.ai/)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [vLLM on AWS Neuron](https://github.com/vllm-project/vllm)
- [Amazon EKS Auto Mode](https://aws.amazon.com/eks/auto-mode/)
- [Langfuse](https://langfuse.com/)
</content>
