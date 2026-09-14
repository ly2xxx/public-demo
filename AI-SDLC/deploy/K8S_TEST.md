
# 1. Populate secrets and deploy Postgres & LiteLLM

kubectl apply -f deploy/base/namespaces.yaml
kubectl apply -f deploy/base/postgres/
kubectl apply -f deploy/base/litellm/

# 2. Port-forward and interact with the gateway

kubectl port-forward -n ai-platform svc/litellm 4000:4000
curl http://localhost:4000/models -H "Authorization: Bearer sk-litellm-master-replace-me"
