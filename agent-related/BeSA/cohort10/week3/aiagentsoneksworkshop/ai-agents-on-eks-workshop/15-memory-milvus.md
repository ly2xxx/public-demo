# Memory Management using Milvus

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/20-self-managed-infrastructure/500-memory-milvus

## At a glance

- **Goal:** Give the agent conversation memory by storing and replaying the customer's own turns from the current session.
- **Prerequisites:** The RAG with Milvus lab

In this module, you give the agent conversation memory using the same Milvus vector database from the RAG with Milvus lab. This time you store the customer's own conversation turns instead of a product catalog. On each new message the agent loads the recent turns from this session and replays them as context, so the customer doesn't have to repeat themselves.

This is the self-managed counterpart to the integrated Memory Management using AgentCore Memory lab. It uses the same capability and access pattern (recent turns per session), built on infrastructure you run yourself.

## Memory vs RAG on Milvus

You've now used Milvus for two different jobs. They share the same storage engine but solve different problems:

| | RAG with Milvus | Memory with Milvus (this lab) |
|---|---|---|
| What's stored | Product catalog + FAQ embeddings (static, shared) | The customer's conversation turns (grows over time) |
| Keyed by | Nothing, one shared catalog | `actor_id` + `session_id` for this customer's session |
| Retrieval | Vector search ("find similar products") | Recency ("this session's recent turns, in order") |
| Purpose | Ground answers in product knowledge | Continue the conversation with context |

## Recency now, semantic later

This lab retrieves by recency within a session. It uses a scalar query on Milvus (no vector search). Each turn is still stored as an embedding, so extending this to semantic cross-session recall is a one-line change: swap the query for a vector search.

## What you'll build

A customer service agent that, across turns in the same conversation:

- Loads the recent turns for this `actor_id` + `session_id` from Milvus
- Replays them into the agent so earlier context (like an order ID) carries forward
- Records each new turn back into Milvus for the next message

## How it works

1. Each turn (customer question + agent answer) is stored in a `conversation_memory` collection, tagged with `actor_id`, `session_id`, and a timestamp.
2. On a new message, the agent runs a scalar query filtered by `actor_id` + `session_id`, sorted by time. The result is the recent turns, oldest first. `consistency_level="Strong"` guarantees the turn just written is immediately visible.
3. Those turns are replayed into the Strands agent as prior messages.
4. The agent answers with that context, then records the new turn.

## Step 1: Verify Milvus

```bash
kubectl get pods -n milvus
```

Same `milvus-standalone`, `etcd`, and `minio` pods from the RAG lab. Memory reuses them, storing a separate `conversation_memory` collection.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/20-self-managed/500-memory-milvus/customer-agent
```

Compared to the RAG lab, `rag_tools.py` is replaced by `memory.py`, and `agent.py` restructures around `run_stream()`, which hydrates the session's recent turns and records the new one. The shape matches the integrated AgentCore lab, but backed by Milvus.

**memory.py — record + recent turns:**

```python
@observe(name="milvus_memory.record_turn")
def record_turn(actor_id, session_id, user_message, assistant_message):
    """Persist one turn (embedded, so semantic recall stays possible later)."""
    _client.insert(COLLECTION, data=[{
        "actor_id": actor_id, "session_id": session_id,
        "user_message": user_message, "assistant_message": assistant_message,
        "ts": int(time.time()), "vector": _embed(user_message),
    }])

@observe(name="milvus_memory.recent_turns")
def recent_turns(actor_id, session_id, max_results=20):
    """This session's turns, oldest first. Scalar query, no vector search."""
    rows = _client.query(
        COLLECTION,
        filter=f'actor_id == "{actor_id}" && session_id == "{session_id}"',
        output_fields=["user_message", "assistant_message", "ts"],
        limit=max_results, consistency_level="Strong",
    )
    ... # sort by ts, flatten to [{role, content}, ...]
```

- Retrieval is a scalar query on `actor_id` + `session_id`. Milvus acts as a filtered store, not a vector search.
- `consistency_level="Strong"` is the key line. Without it, Milvus's default bounded staleness could hide the turn you just wrote, breaking multi-turn recall.
- The turn is still embedded on write, so the collection is ready for semantic recall as an extension.

## Step 3: Deploy the agent

```bash
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent --timeout=180s
```

## Step 4: Chat across turns

Open the chat UI and pick **Customer Agent (Self-managed GenAI)**. The UI sends a stable `session_id` for every message in the same browser tab, so turn 2 can recall turn 1.

Turn 1 (establish context):
- "Hi, I'd like to check on my order ORD-12345."

Turn 2 (same tab, no order ID):
- "Has it shipped yet?"

The agent calls `lookup_order` with `ORD-12345` on its own, pulled from turn 1's stored turn, not from anything you re-typed. The memory layer did the work.

Open a new browser tab or reload the UI and you'll get a fresh `session_id`, so turn 2 won't find turn 1's context. That's the session scoping working as designed, not a bug.

## Step 5: See it in Langfuse

Each turn now shows a `milvus_memory.recent_turns` span (the read) and a `milvus_memory.record_turn` span (the write) nested under the `chat_turn` root. You can watch memory being read before the model call and written after.

## What you built

Session conversation memory on Milvus. The agent carries context across turns instead of treating each message as the first. Same vector database as the RAG lab, a different collection, and a recency access pattern. Semantic recall is one line away, since turns are stored as embeddings.

## What's next

Tools are still in-process. Next you'll move them out to a real MCP server running on EKS in the Agent Tool Access (MCP) lab.
</content>
