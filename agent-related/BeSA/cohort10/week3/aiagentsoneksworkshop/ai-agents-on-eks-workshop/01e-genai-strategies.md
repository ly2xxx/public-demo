# Agentic AI Patterns on AWS

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/10-introduction/400-genai-strategies

Before you start building, let's spend some time understanding the different ways you can deploy AI agents on AWS. Each approach involves distinct trade-offs between control, operational overhead, and time to production. This module walks through three common strategies and helps you decide when to use each one.

## Strategy 1: Self-Managed on Kubernetes

Run open-source models on EKS with full control over every layer: model serving (vLLM), agent framework (Strands), vector DB (Milvus), observability (Langfuse), and tool protocols (MCP, A2A).

| Component | Service |
|---|---|
| Model inference | vLLM on EKS (Inferentia/GPU) |
| Agent orchestration | Strands Agents SDK |
| Memory | Milvus (vector DB on EKS) |
| Tools | MCP server on EKS |
| Observability | Langfuse on EKS |
| Multi-agent | A2A protocol |

**Pros**
- Full control over model selection, fine-tuning, and optimization
- Use any open-source or custom model (no gating restrictions)
- Transparent agent logic. You can debug every step.
- Portable across clouds and on-premises
- Cost-effective at scale with reserved capacity (Inferentia, Spot)

**Cons**
- Higher operational overhead (patching, scaling, monitoring)
- Must manage infrastructure reliability (node failures, storage, networking)
- Longer time to production
- Team needs Kubernetes and ML infrastructure expertise

**Best for:** Teams with specific model requirements, strict data residency needs, or existing Kubernetes expertise who want maximum flexibility.

## Strategy 2: Integrated (Self-Hosted Agents + Managed Agent Capabilities)

Keep the agent framework and orchestration logic in your own code (Strands SDK on EKS), but swap self-hosted backends for AWS managed services: Bedrock for inference, AgentCore for memory and tools.

| Component | Service |
|---|---|
| Model inference | Amazon Bedrock (via LiteLLM proxy) |
| Agent orchestration | Strands Agents SDK (on EKS) |
| Memory | AgentCore Memory |
| Tools | AgentCore Browser, Code Interpreter |
| Observability | Langfuse on EKS |
| Multi-agent | A2A protocol |

**Pros**
- Same agent code as self-managed; only the config changes
- No model hosting or GPU/Inferentia management
- Managed memory and tools reduce operational burden
- LiteLLM proxy makes switching between Bedrock and vLLM a config change
- Full visibility into agent logic (you own the orchestration)

**Cons**
- Still requires EKS for agent pods and observability
- Bedrock model selection is more limited than open-source
- AgentCore services are region-dependent
- Mixed operational model (K8s + managed services)

**Best for:** Teams that want to own the agent logic and orchestration but offload infrastructure-heavy components like model serving and data stores to managed services.

## Strategy 3: Fully Managed

Use AWS managed services end-to-end: Bedrock for model inference, Bedrock Agents for orchestration, and managed tool integrations.

| Component | Service |
|---|---|
| Model inference | Amazon Bedrock |
| Agent orchestration | Bedrock Agents |
| Memory | AgentCore Memory |
| Tools | AgentCore Gateway, Lambda |
| Observability | CloudWatch, Bedrock logging |

**Pros**
- Fastest path to production with no infrastructure to manage
- Automatic scaling, patching, and high availability
- Native integration with AWS security (IAM, VPC, KMS)
- Pay-per-use pricing with no idle costs

**Cons**
- Limited to models available in Bedrock
- Less control over inference parameters and optimization
- Agent orchestration logic is opaque (harder to debug complex flows)

**Best for:** Teams that want to ship fast, don't need custom models, and prefer operational simplicity over fine-grained control.

## Decision Framework

| Question | Self-Managed | Integrated | Fully Managed |
|---|---|---|---|
| Need a specific open-source model? | Yes | No | No |
| Team has Kubernetes expertise? | Required | Required | Not required |
| Data must stay in your VPC? | Yes | Partial | Partial |
| Time to production matters most? | Slow | Middle | Best |
| Want cloud-portable architecture? | Yes | Partial | No |
| Complex multi-agent workflows? | Full control | Full control | Limited |

## What this workshop covers

This workshop gives you hands-on experience with the self-managed and integrated approaches:

| Track | What you'll build |
|---|---|
| Self-Managed on Kubernetes | vLLM on Inferentia → Strands agent → Langfuse → Milvus → MCP → A2A |
| Integrated Architecture | Bedrock via LiteLLM → Strands agent → Langfuse → AgentCore Memory → AgentCore Tools → A2A |

The agent code stays nearly identical across both tracks, only the infrastructure configuration changes. This demonstrates the integrated approach: same SDK, same protocol, different backends.
</content>
