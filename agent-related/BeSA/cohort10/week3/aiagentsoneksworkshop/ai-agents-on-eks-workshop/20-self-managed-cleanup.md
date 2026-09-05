# Cleanup (Self-Managed Track)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/900-cleanup

Clean up the Deployments, Services, and any leftover port-forwards from the self-managed track.

## Agent + MCP workloads

```bash
kubectl delete deployment customer-agent order-agent product-agent orchestrator-agent mcp-server 2>/dev/null
kubectl delete service customer-agent order-agent product-agent orchestrator-agent mcp-server 2>/dev/null
```

## Any leftover port-forward from the vLLM lab

```bash
kill $(lsof -t -i:8000) 2>/dev/null
```

## What persists (by design)

These steps remove the Deployments and Services you created, but some resources are left in place on purpose:

- **Seeded data** — the product catalog in Milvus and the graph in Neo4j
- **ECR images** — the container images built during the labs
- **Shared infrastructure** — the LiteLLM proxy, vLLM, Langfuse, Milvus, and Neo4j themselves (managed by Terraform)

You don't need to delete these manually — they are all torn down when the workshop environment is destroyed at the end.
</content>
