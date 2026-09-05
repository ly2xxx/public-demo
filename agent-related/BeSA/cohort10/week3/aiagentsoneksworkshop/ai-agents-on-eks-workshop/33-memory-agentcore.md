# Memory Management using AgentCore Memory

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/300-memory-agentcore

## At a glance

- **Goal:** Add Amazon Bedrock AgentCore Memory so the agent recalls earlier turns in a session, without touching the model plane.
- **Prerequisites:** The Agents using Strands with Bedrock lab

In this module, you'll add Amazon Bedrock AgentCore Memory so the agent remembers what each customer asked earlier in the session. The model plane stays the same (`OpenAIModel` pointed at LiteLLM with `model_id="nova-lite"`), and only the memory layer changes.

Unlike the self-managed RAG with Milvus lab, this isn't a direct swap. AgentCore Memory and Milvus solve different problems:

| | Self-managed: Milvus | Integrated: AgentCore Memory (this module) |
|---|---|---|
| What it stores | Product catalog + FAQ embeddings | Conversation events per customer session |
| Access pattern | Vector search ("find similar products") | Event history, retrieval by session/actor |
| Use-case | Retrieval-Augmented Generation | Session memory and personalization |

Conversational memory and knowledge retrieval are complementary but serve different purposes. This module focuses on conversational memory, which is what AgentCore Memory is designed for: storing and recalling session history across interactions. For knowledge retrieval use cases such as product catalog search, you can continue using Milvus or adopt Amazon Bedrock Knowledge Bases.

## What you'll build

A customer service agent that, across separate invocations for the same customer:

- Remembers what the customer asked earlier in the session
- Recognizes repeat customers
- Uses past context to shape responses

## Step 1: Confirm the memory resource

Terraform has already provisioned an AgentCore Memory resource and stored its ID in the `agent-config` ConfigMap:

```bash
kubectl get configmap agent-config -n agents -o yaml | grep AGENTCORE
```

You should see `AGENTCORE_MEMORY_ID` and `AGENTCORE_MEMORY_ARN`. The agent ServiceAccount already has IAM permissions to write and read events.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/300-memory-agentcore/customer-agent
```

New file: `memory.py`, a thin boto3 wrapper. `agent.py` restructures around a `run()` that hydrates past turns and records the new one.

**memory.py — event I/O:**

```python
@observe(name="agentcore_memory.record_turn")
def record_turn(actor_id, session_id, user_message, assistant_message):
    """Persist one turn (user + assistant) as an event."""
    _client.create_event(
        memoryId=MEMORY_ID,
        actorId=actor_id,
        sessionId=session_id,
        eventTimestamp=datetime.now(timezone.utc),
        payload=[
            {"conversational": {"role": "USER", "content": {"text": user_message}}},
            {"conversational": {"role": "ASSISTANT", "content": {"text": assistant_message}}},
        ],
    )

@observe(name="agentcore_memory.recent_turns")
def recent_turns(actor_id, session_id, max_results=20):
    """Return recent turns, oldest first."""
    resp = _client.list_events(
        memoryId=MEMORY_ID, actorId=actor_id, sessionId=session_id,
        maxResults=max_results, includePayloads=True,
    )
    turns = []
    for event in reversed(resp.get("events", [])):
        for item in event.get("payload", []):
            ...
```

- `actorId` = customer identity (email, customer ID). `sessionId` = one conversation
- `list_events` returns newest first; we reverse to read chronologically
- Events expire after 30 days (set in `terraform/agentcore.tf`)
- `@observe` wraps each call in a Langfuse span so memory reads and writes show up alongside the LLM/tool spans. Strands' OTel only covers the agent loop, so without this decorator the memory calls would be invisible in traces.

## Step 3: Deploy (image already built)

The `customer-agent:agentcore-memory` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/30-integrated/300-memory-agentcore/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent -n agents --timeout=120s
```

## Step 4: Chat across turns

Open the chat UI, pick **Customer Agent (Integrated GenAI)**. The UI passes a stable `session_id` for every message in the same browser tab, so turn 2 can recall turn 1.

Turn 1 (establish context):
- "Hi, I'd like to check on my order ORD-12345."

Turn 2 (same tab, no order ID):
- "Has it shipped yet?"

The agent should call `lookup_order` with `ORD-12345` on its own, pulled from turn 1's event history. No prompting, no hints.

Open a new browser tab or reload the UI, and you'll get a fresh session ID. Turn 2 won't find turn 1's context. That's the mechanism doing its job, not a bug.

In Langfuse, each conversation turn now appears as a single end-to-end trace. The `chat_turn` span serves as the root, with four child spans nested beneath it: the memory read, the Strands agent loop, the LiteLLM proxy spans, and the memory write.

## Step 5: Inspect the stored events

```bash
MEMORY_ID=$(kubectl get cm agent-config -n agents -o jsonpath='{.data.AGENTCORE_MEMORY_ID}')
SESSION_ID=$(kubectl logs -n agents deployment/customer-agent --tail=200 | grep -oE 'ui-[a-f0-9-]+' | tail -1)
echo "Memory: $MEMORY_ID"
echo "Session: $SESSION_ID"

aws bedrock-agentcore list-events \
  --memory-id "$MEMORY_ID" \
  --actor-id "workshop-user" \
  --session-id "$SESSION_ID" \
  --include-payloads
```

Two events, each with both turns.

## What you changed

- Added `memory.py` (plain boto3, no new SDKs)
- Wrapped the agent in a `run()` that hydrates history and records the new turn
- Dropped Milvus, torch, and sentence-transformers. The image is materially smaller.

## What's next

The agent now remembers. Next, give it two new tools: AgentCore Code Interpreter and AgentCore Browser. So it can do sandboxed work outside its own process.
</content>
