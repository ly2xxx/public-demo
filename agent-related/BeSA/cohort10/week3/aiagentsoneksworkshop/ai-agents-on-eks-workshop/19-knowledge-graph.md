# Knowledge Graph with Neo4j

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/800-knowledge-graph

## At a glance

- **Goal:** Model the shop as a knowledge graph in Neo4j and answer multi-hop questions by traversing relationships instead of searching vectors.
- **Prerequisites:** The RAG with Milvus lab

In this module, you connect the agent to a knowledge graph. The shop's customers, orders, products, categories, and policies become nodes and relationships in [Neo4j](https://neo4j.com/), and the agent answers questions by traversing them — questions vector search can't answer, like "what do people who bought this laptop usually buy with it?"

## Graph vs vector search

You built RAG on Milvus in the RAG with Milvus lab. Both are retrieval, but they answer different questions:

| | RAG with Milvus | Knowledge graph (this lab) |
|---|---|---|
| Data shape | Embeddings (points in vector space) | Nodes + typed relationships |
| Query | "What is similar to this text?" | "What is connected to this thing, and how?" |
| Strength | Fuzzy matching, unstructured text | Multi-hop questions, precise joins |
| Example | "noise cancelling headphones" → product description | "customers who bought X also bought…" → 4-hop traversal |

Neither replaces the other. Production agents often combine them (GraphRAG): vector search finds the entry-point entity, the graph expands from it.

## The ontology

A knowledge graph without a schema drifts into mush. This one is constrained to five node types and four relationship types — the ontology:

```
(:Customer)-[:PLACED]->(:Order)-[:CONTAINS {qty}]->(:Product)
(:Product)-[:IN_CATEGORY]->(:Category)-[:HAS_POLICY]->(:Policy)
```

Same shop data as every other lab — the three orders from the MCP lab, the products from the Milvus catalog — plus a few historical orders so traversals have somewhere to go. What's new isn't the data. It's that the relationships are now first-class and queryable.

## What you'll build

A customer service agent whose four tools are each one fixed Cypher traversal:

- `lookup_order` — order → items → customer (the same lookup as before, now a graph walk)
- `customer_history` — customer → all orders → items
- `recommend_products` — product → orders containing it → those customers → their other orders → co-purchased products (4 hops)
- `product_policies` — product → category → policies

The LLM picks the tool and fills in parameters; it never writes Cypher. That keeps a 3B model reliable. Text-to-Cypher — letting the LLM generate queries — is a natural extension once you've seen the fixed-tool version work.

## Step 1: Verify Neo4j

Neo4j Community was deployed during provisioning (like Milvus, via Helm):

```bash
kubectl get pods -n neo4j
```

You should see a `neo4j-0` pod. Export the password into your shell — the seed job in Step 3 reads it, and you sign in to the Browser UI with it in Step 4:

```bash
export NEO4J_PASSWORD=$(kubectl get configmap agent-config -o jsonpath='{.data.NEO4J_PASSWORD}')
echo $NEO4J_PASSWORD
```

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/20-self-managed/800-knowledge-graph/customer-agent
```

Compared to the RAG lab, `rag_tools.py` is replaced by `graph_tools.py`, and the seeder writes nodes and relationships instead of embeddings. No embedding model at all — the Dockerfile drops the multi-stage fastembed build and goes back to the simple single-stage image.

**graph_tools.py — traversals as tools:**

```python
@tool
@observe(name="graph.recommend_products")
def recommend_products(product_name: str) -> list:
    """Recommend products often bought by customers who bought this product."""
    rows = _rows(
        """
        MATCH (p:Product)<-[:CONTAINS]-(:Order)<-[:PLACED]-(c:Customer)
              -[:PLACED]->(:Order)-[:CONTAINS]->(rec:Product)
        WHERE toLower(p.name) CONTAINS toLower($name) AND rec <> p
        RETURN rec.name AS product, rec.price AS price, count(DISTINCT c) AS bought_by
        ORDER BY bought_by DESC, product
        """,
        name=product_name,
    )
```

- The highlighted `MATCH` is the whole point of this lab: product → orders → customers → their other orders → products. Four hops, one declarative pattern. Try writing that against a vector index.
- The neo4j driver is module-level and thread-safe with built-in pooling — unlike the Milvus client, no caveats needed.
- Parameters (`$name`) are passed separately, never interpolated into the query string. Same injection rule as SQL.

## Step 3: Seed the graph

Like the Milvus lab, the seeder ships inside the agent image and runs in-cluster:

```bash
IMG=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/customer-agent:graph
kubectl run graph-seed --rm -i --restart=Never \
  --image=$IMG \
  --image-pull-policy=Always \
  --env="NEO4J_URI=neo4j://neo4j.neo4j.svc.cluster.local:7687" \
  --env="NEO4J_PASSWORD=$NEO4J_PASSWORD" \
  --command -- python seed_graph.py
```

You should see node counts by label and a test traversal listing what Laptop Pro 15 buyers also bought.

## Step 4: See the graph in Neo4j Browser

This is the part no other lab has: look at your data as a graph. Neo4j's Browser UI is exposed through a load balancer. Print the URL and the password together:

```bash
echo "Neo4j Browser: http://$(kubectl get svc -n neo4j neo4j-lb-neo4j -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'):7474"
echo "Username: neo4j"
echo "Password: $(kubectl get configmap agent-config -o jsonpath='{.data.NEO4J_PASSWORD}')"
```

Open the URL and sign in. Leave the connect URL in the dialog as suggested.

Once connected, the left panel shows the database: 25 nodes across the five labels of the ontology, 31 relationships.

Then run:

```cypher
MATCH (c:Customer)-[r1:PLACED]->(o:Order)-[r2:CONTAINS]->(p:Product)
RETURN c, r1, o, r2, p
```

You get the interactive graph — customers, orders, products as draggable nodes. Click any node to inspect its properties. This is the same data your agent traverses.

### The 4-hop recommendation, visually

Run the recommendation traversal in the Browser and watch the path light up:

```cypher
MATCH path = (:Product {name: 'Laptop Pro 15'})<-[:CONTAINS]-(:Order)
  <-[:PLACED]-(:Customer)-[:PLACED]->(:Order)-[:CONTAINS]->(rec:Product)
WHERE rec.name <> 'Laptop Pro 15'
RETURN path
```

## Step 5: Deploy the agent

```bash
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=180s
```

## Step 6: Chat

Open the chat UI, pick **Customer Agent (Self-managed GenAI)**, and ask graph-shaped questions:

- "What do people who bought the Laptop Pro 15 usually buy with it?"
- "What has Jane Doe ordered before?"
- "What's the warranty on the Noise Cancelling Headphones?"

The first one is the co-purchase traversal — an answer that doesn't exist in any single record, only in the connections.

In Langfuse, each turn shows a `graph.*` span with the traversal's inputs and returned rows.

## What you built

A knowledge graph with an explicit ontology, and an agent whose tools are graph traversals. Multi-hop questions (co-purchases, customer history, policy-via-category) resolve as single declarative queries against relationships — the class of question RAG alone can't answer. And you can see the graph in Neo4j Browser, which is worth a thousand JSON blobs.

## Self-managed track summary

Next up: same agent, managed capabilities. Bedrock + AgentCore, same EKS. The only agent-side change is `model_id="nova-lite"`, because LiteLLM is doing the backend swap for you.
</content>
