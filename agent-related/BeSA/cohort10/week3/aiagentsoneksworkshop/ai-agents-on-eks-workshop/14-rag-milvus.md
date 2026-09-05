# RAG with Milvus

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/400-rag-milvus

## At a glance

- **Goal:** Ground the agent's product answers in the real catalog with retrieval-augmented generation over Milvus.
- **Prerequisites:** The Agents using Strands lab

In this module, you connect the agent to a product catalog using Retrieval-Augmented Generation (RAG). Milvus is already deployed in your environment. Once connected, the agent answers product questions (such as "Do you have wireless headphones under $100?") with grounded results instead of guesses.

## What is Milvus?

[Milvus](https://milvus.io/) is an open-source vector database built for similarity search at scale. You store data as high-dimensional vectors (embeddings), then query by "find me the vectors closest to this one." It supports multiple index types (IVF, HNSW, DiskANN), hybrid search (vector + scalar filters), and scales from a single-pod standalone mode to a distributed cluster.

## How it works

1. Product descriptions stored in Milvus as vector embeddings
2. Customer asks a product question → agent calls `search_products`
3. The tool embeds the query with `fastembed` (ONNX runtime, same `all-MiniLM-L6-v2` weights) and searches Milvus for similar entries
4. LLM uses the matches to write a helpful answer

## Step 1: Verify Milvus

```bash
kubectl get pods -n milvus
```

You should see `milvus-standalone`, `etcd`, and `minio` pods running.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/20-self-managed/400-rag-milvus/customer-agent
```

This module introduces two new files compared to the Observability using Langfuse lab: `rag_tools.py`, which defines the product search tool, and `seed_products.py`, which loads the catalog into Milvus as a one-time setup step. Beyond those additions, the changes are minimal. `agent.py` adds a single import, and the Dockerfile switches to a multi-stage build so the embedding model weights are bundled into the final image.

**rag_tools.py — the search tool:**

```python
_embedder = TextEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    cache_dir="/app/.fastembed_cache",
)
_client = MilvusClient(uri=MILVUS_URI)

@tool
def search_products(query: str, limit: int = 5) -> list:
    """Search the AnyCompany Shop product catalog and FAQs.

    Use this when a customer asks about products, pricing, shipping, returns, or warranties.
    """
    embeddings = [v.tolist() for v in _embedder.embed([query])]
    results = _client.search(COLLECTION, data=embeddings, ...)
```

- `fastembed` is a lightweight embedding library from Qdrant that runs the `all-MiniLM-L6-v2` model via ONNX runtime. No Python ML framework in the image.
- Embedder and Milvus client are module-level, loaded once at import, reused across calls. The Milvus client isn't thread-safe; pool it for multi-threaded agents.
- The docstring's first line tells the LLM when to pick this tool. That's the selection heuristic.

## Step 3: Seed the product catalog

`seed_products.py` defines ~13 products and FAQs, embeds them, and inserts into a `product_catalog` collection. Rather than installing `fastembed` + `pymilvus` on your IDE for a one-shot seed, we ship the script inside the customer-agent image and run it from a pod in the cluster.

The `customer-agent:milvus` image was pre-built and pushed to ECR during provisioning, so run the seeder directly:

```bash
IMG=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/customer-agent:milvus
kubectl run milvus-seed --rm -i --restart=Never \
  --image=$IMG \
  --image-pull-policy=Always \
  --env="MILVUS_URI=http://milvus.milvus.svc.cluster.local:19530" \
  --command -- python seed_products.py
```

You should see "Inserted 13 items" and a test search for "wireless headphones" returning matches. The pod disappears when the script exits.

## Step 4: Deploy the agent

```bash
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=180s
```

## Step 5: Chat

Open the chat UI, pick **Customer Agent (Self-managed GenAI)**, and try product questions:

- "What's your return policy?"
- "Do you have any noise cancelling headphones?"
- "Is the Laptop Pro under warranty?"

In Langfuse, note the new `search_products` span, typically 50-200ms for the embedding + search.

## What you built

The agent has two tools now: `lookup_order` for specific orders and `search_products` for catalog/FAQ questions. Product knowledge is backed by real embeddings, not a hardcoded switch statement.

## What's next

Orders are still mocked inside the agent process. Next you'll move tools out to a real MCP server running on EKS.
</content>
