# Cleanup (Integrated Track)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/600-cleanup

Cleanup the Deployments, Services, and any leftover resources from the integrated track. All resources live in the `agents` namespace.

## Multi-agent workloads (Module 500)

```bash
kubectl delete deployment orchestrator-agent order-agent sandbox-agent mcp-server -n agents 2>/dev/null
kubectl delete service orchestrator-agent order-agent sandbox-agent mcp-server -n agents 2>/dev/null
```

## Single-agent workloads (Modules 100–400)

Each module reuses the same `customer-agent` Deployment and Service, so one delete covers all of them:

```bash
kubectl delete deployment customer-agent -n agents 2>/dev/null
kubectl delete service customer-agent -n agents 2>/dev/null
```

## Verify nothing is left

```bash
kubectl get deployments,services -n agents
```

You should see only the agent ServiceAccount and the pre-provisioned ConfigMaps (`agent-config`, `agent-tools`). Those are managed by Terraform and will be cleaned up when the workshop environment is destroyed.

## Managed AgentCore resources (persist by design)

Unlike the in-cluster workloads above, the AWS-managed resources you created live outside the `agents` namespace and are not removed by `kubectl delete`:

- **AgentCore Memory events** — the session events written in the Memory lab remain in the memory store
- **Custom evaluator** — the `cs_accuracy` evaluator created in the Evaluation lab stays ACTIVE in your account

These are cleaned up when the workshop environment is destroyed, so you don't need to touch them. If you want to remove the custom evaluator explicitly (for example to re-run the Evaluation lab cleanly):

```bash
CUSTOM_ID=$(aws bedrock-agentcore-control list-evaluators --region $AWS_REGION \
  --query "evaluators[?evaluatorType=='Custom'].evaluatorId | [0]" --output text)
aws bedrock-agentcore-control delete-evaluator --evaluator-id "$CUSTOM_ID" --region $AWS_REGION
```
</content>
