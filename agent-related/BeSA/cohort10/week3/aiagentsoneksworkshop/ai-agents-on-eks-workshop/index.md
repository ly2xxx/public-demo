# Building Production Ready AI Agents on Amazon EKS

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US

A hands-on AWS workshop that builds a customer service agent for a fictional online store (AnyCompany Shop), then evolves it across two infrastructure strategies: fully self-managed on EKS, and integrated with AWS managed services (Bedrock, AgentCore). Both tracks land on the same working multi-agent system with observability, memory, tool access, and sandboxed execution.

## Overview & Introduction

| File | Page |
|---|---|
| [00-workshop-overview.md](00-workshop-overview.md) | Welcome, what you'll learn, workshop structure, target audience, prerequisites |
| [01-introduction.md](01-introduction.md) | Introduction — section index |
| [01a-start-with-event.md](01a-start-with-event.md) | Start with AWS Event — accessing your Workshop Studio account |
| [01b-terminal-instructions.md](01b-terminal-instructions.md) | Terminal instructions — IDE, pasting commands, AWS Console access |
| [01c-lab-structure.md](01c-lab-structure.md) | Workshop Structure — environment layout, code layout, Terraform state |
| [01d-sample-application.md](01d-sample-application.md) | Sample Application — AnyCompany Shop, data model, chat UI |
| [01e-genai-strategies.md](01e-genai-strategies.md) | Agentic AI Patterns on AWS — self-managed vs. integrated vs. fully-managed strategy comparison |

## Track 1: Self-Managed GenAI Strategy (EKS-native, open source)

| File | Page |
|---|---|
| [10-self-managed-overview.md](10-self-managed-overview.md) | Self-Managed GenAI Strategy — architecture overview & lab list |
| [11-vllm-on-eks.md](11-vllm-on-eks.md) | Model Plane: vLLM + LiteLLM on EKS |
| [12-strands-agents.md](12-strands-agents.md) | Agents using Strands |
| [13-observability-langfuse.md](13-observability-langfuse.md) | Observability using Langfuse |
| [14-rag-milvus.md](14-rag-milvus.md) | RAG with Milvus |
| [15-memory-milvus.md](15-memory-milvus.md) | Memory Management using Milvus |
| [16-agent-tools-mcp.md](16-agent-tools-mcp.md) | Agent Tool Access (MCP) |
| [17-multi-agent-a2a.md](17-multi-agent-a2a.md) | Multi-Agent Interaction (A2A) |
| [18-evaluation-llm-judge.md](18-evaluation-llm-judge.md) | Evaluation with LLM-as-a-Judge |
| [19-knowledge-graph.md](19-knowledge-graph.md) | Knowledge Graph with Neo4j |
| [20-self-managed-cleanup.md](20-self-managed-cleanup.md) | Cleanup (self-managed track) |

## Track 2: Integrated GenAI Strategy (EKS + AWS managed services)

| File | Page |
|---|---|
| [30-integrated-overview.md](30-integrated-overview.md) | Integrated GenAI Strategy — architecture overview & module list |
| [31-strands-bedrock.md](31-strands-bedrock.md) | Agents using Strands with Bedrock |
| [32-observability-langfuse-bedrock.md](32-observability-langfuse-bedrock.md) | Observability using Langfuse (integrated) |
| [33-memory-agentcore.md](33-memory-agentcore.md) | Memory Management using AgentCore Memory |
| [34-managed-tools.md](34-managed-tools.md) | Managed Capabilities (Browser + Code Interpreter) |
| [35-multi-agent-a2a-bedrock.md](35-multi-agent-a2a-bedrock.md) | Multi-Agent Interaction (A2A) (integrated) |
| [36-evaluation-agentcore.md](36-evaluation-agentcore.md) | Evaluation with AgentCore |
| [37-integrated-cleanup.md](37-integrated-cleanup.md) | Cleanup (integrated track) |

## Wrap-up

| File | Page |
|---|---|
| [40-summary.md](40-summary.md) | Summary — what you built, the point, next steps |

## The shared thread

Both tracks put the same customer-service agent (Strands SDK) behind one LiteLLM proxy. Swapping infrastructure — self-hosted vLLM/Qwen2.5-3B vs. Amazon Bedrock/Nova, Milvus vs. AgentCore Memory, an in-cluster MCP server vs. AgentCore Browser/Code Interpreter — is a one-line `model_id` or backend config change; the agent code, A2A protocol, and Langfuse observability layer stay identical across both.
</content>
