# Workshop Structure

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/10-introduction/300-lab-structure

Your environment is already stocked. Here's what's waiting for you:

- An Amazon EKS cluster (Auto Mode)
- vLLM serving Qwen2.5-3B on AWS Inferentia accelerators
- Langfuse for observability
- Amazon Bedrock AgentCore memory, browser, and code interpreter, pre-provisioned for the Integrated GenAI strategy
- A VS Code IDE in the browser (your command center)

## Access the EKS Cluster

From your IDE terminal:

```bash
kubectl get nodes
```

Nodes should be `Ready`. Check vLLM is up too:

```bash
kubectl get pods -n vllm -l app=qwen2-5-3b-neuron
```

## Workshop code layout

Every module ships its complete end-state under `~/environment/modules/`. You don't type code into heredocs, each module starts with a `cd` into its project directory, and you open the files directly in the IDE.

```bash
ls ~/environment/modules
```

You should see two track directories:

```
modules/
├── 20-self-managed/
│   ├── 200-strands-agents/customer-agent/
│   ├── 300-observability-langfuse/customer-agent/
│   ├── 400-rag-milvus/customer-agent/
│   ├── 500-memory-milvus/customer-agent/
│   ├── 600-agent-tools-mcp/{customer-agent,mcp-server}/
│   ├── 700-multi-agent-a2a/a2a-agents/
│   └── 800-knowledge-graph/customer-agent/
└── 30-integrated/
    ├── 100-strands-bedrock/customer-agent/
    ├── 200-observability-langfuse/customer-agent/
    ├── 300-memory-agentcore/customer-agent/
    ├── 400-managed-tools/customer-agent/
    └── 500-multi-agent-a2a/a2a-integrated/
```

## Reset to a clean slate (only if you need to)

Edited the wrong file and want to start over? The command below overwrites your local changes under `~/environment/modules/` with the shipped version. Don't run it unless that's what you want.

```bash
unzip -o /tmp/modules.zip -d ~/environment/modules/
```

## Terraform state

The EKS cluster, operational addons, and other AWS services (vLLM, Langfuse, Milvus, ECR, AgentCore) are already up. Source lives at `~/environment/terraform/` if you want to poke around.
</content>
