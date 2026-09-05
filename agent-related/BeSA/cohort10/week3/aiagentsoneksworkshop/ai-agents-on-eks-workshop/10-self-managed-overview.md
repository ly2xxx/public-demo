# Self-Managed GenAI Strategy

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure

Everything runs on Amazon EKS. No managed AI services, just pods, Helm charts, and a bit of Python.

## Architecture Overview

```
EKS Cluster (Auto Mode)
├── Inferentia Node Pool
│   └── vLLM (Qwen2.5-3B on Neuron)
├── litellm namespace
│   └── LiteLLM proxy (shared model plane for both tracks)
├── General Purpose Nodes
│   ├── Strands Agent
│   ├── Langfuse (Observability)
│   ├── Milvus (Vector DB / Memory)
│   ├── Neo4j (Knowledge Graph)
│   └── MCP Server (Agent Tools)
└── Services
    ├── litellm.litellm:4000 (OpenAI-compatible proxy, the one URL agents talk to)
    ├── qwen2-5-3b-neuron.vllm:8000 (upstream backend for LiteLLM)
    ├── langfuse:3000
    ├── milvus:19530
    └── neo4j:7687
```

This diagram shows the end state of the track. Components come online progressively — each lab deploys only the piece it needs, so you won't have all of these running until you've completed every lab. Neo4j, for example, is introduced in the final lab (Knowledge graph).

## Labs

- **Model plane (vLLM + LiteLLM) on EKS:** how the self-hosted model is served and fronted by LiteLLM
- **Agents using Strands:** build and deploy the agent against the shared model plane
- **Observability using Langfuse:** trace every LLM call and tool invocation
- **RAG with Milvus:** add a product catalog with vector search
- **Memory management using Milvus:** recall a customer's past turns with semantic search
- **Agent tool access (MCP):** give the agent tools over the MCP protocol
- **Multi-agent interaction (A2A):** split one agent into specialists
- **Evaluation with LLM-as-a-Judge:** score every conversation on quality using Langfuse
- **Knowledge graph with Neo4j:** traverse relationships vector search can't answer
</content>
