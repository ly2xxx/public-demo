# Evaluation with AgentCore

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/550-evaluation-agentcore

## At a glance

- **Goal:** Score the integrated agent's conversations with Amazon Bedrock AgentCore Evaluations, using two built-in evaluators and one custom retail evaluator you create.
- **Prerequisites:** The Memory Management using AgentCore Memory lab

Your integrated agent is built, memory-backed, and traced, but a trace only tells you what the agent did. It does not tell you whether the answer was any good.

In this module you add automated quality scoring with Amazon Bedrock AgentCore Evaluations, a managed service that grades agent traces with LLM-as-a-Judge. You use two pre-built evaluators as they ship and write one of your own.

This is the managed counterpart to the self-managed Evaluation with LLM-as-a-Judge lab, which wired judging inside Langfuse. Here the judging is a Bedrock service, and the only agent-side change is where traces are sent.

## What is AgentCore Evaluations?

AgentCore Evaluations measures how well an agent performs on accuracy, helpfulness, goal completion, tool selection, and safety. It converts agent traces to a common format and scores them with LLM-as-a-Judge. No ground-truth dataset required.

## Evaluation dimensions for AnyCompany Shop

| Dimension | Evaluator | Question it answers | Why it matters |
|---|---|---|---|
| Correctness | `Builtin.Correctness` | Are the facts in the reply consistent with the tool results? | Hallucinated order status or prices erode customer trust |
| Helpfulness | `Builtin.Helpfulness` | Does the reply resolve the customer's request clearly? | A correct-but-vague reply still creates a follow-up contact |
| Accuracy | `cs_accuracy` (custom) | Did the agent ground its answer in a real `lookup_order` result rather than inventing order details? | A retail-specific check the built-ins cannot express |

## Where traces go in this track

Every other integrated module traces only to Langfuse. AgentCore Evaluations reads traces from AgentCore Observability (CloudWatch and X-Ray) instead, so this module's agent dual-exports every OpenTelemetry span:

```
Customer-agent pod (agents namespace)
Strands → OTel spans
    │
    ├── LangfuseSpanProcessor ─────────▶ Langfuse (AnyCompany Shop project) [unchanged view]
    │
    └── OTLPAwsSpanExporter (SigV4) ───▶ X-Ray OTLP endpoint
                                          │ (Transaction Search → aws/spans)
                                          ▼
                                    AgentCore Observability
                                          │
                                          ▼
                                    AgentCore Evaluations
                                      Builtin.Correctness
                                      Builtin.Helpfulness
                                      cs_accuracy (custom, TRACE level)
```

Both exporters hang off one global `TracerProvider`. The trace tree in Langfuse is identical to the other modules, and the same spans are also queryable in the CloudWatch GenAI Observability console, which is what the evaluators read.

## Step 1: Confirm the evaluation prerequisites

Terraform provisions everything the service needs: the CloudWatch log group traces land in, IAM permissions on the agent ServiceAccount to emit spans and run evaluations and invoke the judge model, an evaluation execution role, and account-level CloudWatch Transaction Search.

Confirm the config the agent and the eval commands read:

```bash
kubectl get configmap agent-config -n agents -o jsonpath='{.data.AGENTCORE_LOG_GROUP}'; echo
kubectl get configmap agent-config -n agents -o jsonpath='{.data.AGENTCORE_EVAL_ROLE_ARN}'; echo
```

Expect the log group `/aws/bedrock-agentcore/runtimes/customer-agent-eval` and the eval execution role ARN.

Transaction Search is account-level. Enabling it routes X-Ray trace segments to CloudWatch Logs for the whole account and region, not just this agent. Terraform enables it for you. In a shared account, know that this is a global setting.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/550-evaluation-agentcore/customer-agent
```

The agent is the AgentCore Memory agent plus one new file, `telemetry.py`, and two small edits to `agent.py`. `tools.py` and `memory.py` are unchanged.

**telemetry.py — dual export:**

```python
from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from amazon.opentelemetry.distro.exporter.otlp.aws.traces.otlp_aws_span_exporter import OTLPAwsSpanExporter

def init_tracing() -> Langfuse:
    # Resource attributes that make AgentCore Observability + Evaluations treat
    # this EKS agent like a first-class agent (a Runtime-hosted agent gets these
    # for free; we set them explicitly):
    resource = Resource.create({
        "service.name": SERVICE_NAME,
        "aws.log.group.names": AGENT_LOG_GROUP,  # associates spans with the log group
        "aws.service.type": "gen_ai_agent",       # the eval span-query filters on this
        "cloud.resource_id": f"runtime/{AGENT_ID}/eval",  # eval parses agent id from here
    })
    provider = TracerProvider(resource=resource)

    # AgentCore Observability — SigV4 OTLP to the X-Ray endpoint. The endpoint
    # MUST be explicit; the exporter defaults to localhost:4318 otherwise.
    aws_exporter = OTLPAwsSpanExporter(
        endpoint=f"https://xray.{REGION}.amazonaws.com/v1/traces",
        aws_region=REGION, session=boto3.Session(),
    )
    provider.add_span_processor(BatchSpanProcessor(aws_exporter))
    trace.set_tracer_provider(provider)

    # Langfuse (v4) attaches its OWN processor to the SAME provider, so spans go
    # to both backends. Use the returned client; do NOT call get_client().
    return Langfuse(tracer_provider=provider,
                     public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                     secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                     host=os.environ.get("LANGFUSE_BASE_URL"))
```

- One global `TracerProvider` feeds both the AWS X-Ray exporter and Langfuse, so every span reaches both backends.
- The three resource attributes are how AgentCore Evaluations finds these spans. It queries the `aws/spans` log group filtering on `aws.service.type = "gen_ai_agent"` and parses the agent id out of `cloud.resource_id`.
- In Langfuse v4 you do not construct `LangfuseSpanProcessor` by hand. Pass the provider to `Langfuse(tracer_provider=...)` and it wires its own processor.

## Step 3: Deploy

The `customer-agent:agentcore-eval` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/30-integrated/550-evaluation-agentcore/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent -n agents --timeout=120s
```

## Step 4: Generate traces

Open the chat UI, pick **Customer Agent (Integrated GenAI)**, and run two turns so there is material to score:

- "Where is my order ORD-12345?"
- "Has it shipped yet?"

Now confirm the traces reached AgentCore Observability. Allow 60 to 90 seconds of indexing lag after chatting. Transaction Search ingests OTLP spans into the `aws/spans` log group, so that is where to look rather than the per-agent log group:

```bash
START=$(( ($(date +%s) - 600) * 1000 ))
aws logs filter-log-events --region $AWS_REGION --log-group-name "aws/spans" \
  --start-time "$START" --max-items 200 --query 'events[].message' --output json \
  | jq '[ .[] | fromjson | select(.resource.attributes."service.name" == "customer-agent-eval") ] | length'
```

You need a non-zero count before evaluating. You can also open the CloudWatch GenAI Observability console and see the same conversation you are viewing in Langfuse.

## Step 5: Create the custom evaluator

Three evaluators, but you only create one. The two built-ins ship with the service:

| Evaluator | Created how | What you do |
|---|---|---|
| `Builtin.Correctness` | Ships with the service | Nothing, reference the ID |
| `Builtin.Helpfulness` | Ships with the service | Nothing, reference the ID |
| `cs_accuracy` | You create it once | One create-evaluator call |

Evaluator management lives in the `bedrock-agentcore-control` CLI. Running an evaluation uses the data-plane `bedrock-agentcore` CLI in Step 6. Run all of this from the workshop IDE terminal.

List the built-ins to confirm they are available:

```bash
aws bedrock-agentcore-control list-evaluators --region $AWS_REGION \
  --query "evaluators[?evaluatorType=='Builtin'].evaluatorId" --output text
```

Now create `cs_accuracy`, a trace-level judge for retail grounding. The config is sizeable JSON, so write it to a file first:

```bash
cat > /tmp/cs_accuracy_config.json <<'JSON'
{
  "llmAsAJudge": {
    "instructions": "You are a senior customer-service QA auditor for an online retailer. Evaluate the ACCURACY of this agent interaction.\n\nContext (conversation + tool calls): {context}\n\nAgent response: {assistant_turn}\n\nDid the agent call lookup_order instead of guessing? Are order details, statuses, prices, and tracking consistent with the tool result? Did it avoid inventing any order or detail not returned by a tool?",
    "ratingScale": {
      "numerical": [
        {"label": "Grounded", "definition": "Fully grounded in tool results, no invented details", "value": 1.0},
        {"label": "Partial", "definition": "Mostly grounded, minor unsupported detail", "value": 0.5},
        {"label": "Invented", "definition": "Invented order details or ignored tool results", "value": 0.0}
      ]
    },
    "modelConfig": {
      "bedrockEvaluatorModelConfig": {
        "modelId": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
      }
    }
  }
}
JSON

CUSTOM_ID=$(aws bedrock-agentcore-control create-evaluator \
  --region $AWS_REGION \
  --evaluator-name cs_accuracy \
  --level TRACE \
  --description "Retail order-accuracy evaluator (tool-grounded)" \
  --evaluator-config file:///tmp/cs_accuracy_config.json \
  --query 'evaluatorId' --output text)

echo "Created custom evaluator: $CUSTOM_ID"
```

`create-evaluator` returns the `evaluatorId` with a suffix appended, such as `cs_accuracy-0ILEKmG3jn`, and `status: ACTIVE`. The evaluator now appears as ACTIVE and Custom in the AgentCore console under Evaluations → Evaluators, and in `list-evaluators` alongside the 16 built-ins.

## Step 6: Run an on-demand evaluation

On-demand evaluation scores one conversation. You give `aws bedrock-agentcore evaluate` the conversation's spans and an evaluator, and it returns a score. All CLI, no code.

**6a. Get the session ID to score.** The chat UI assigns one per conversation. Pull the most recent from the agent logs:

```bash
SESSION_ID=$(kubectl logs -n agents deployment/customer-agent --tail=100 \
  | grep -oE 'session=[^ ]+' | tail -1 | cut -d= -f2)
echo "Scoring session: $SESSION_ID"
```

**6b. Confirm the custom evaluator ID.** You captured it in Step 5. This re-fetches it if your shell is new:

```bash
if [ -z "$CUSTOM_ID" ]; then
  CUSTOM_ID=$(aws bedrock-agentcore-control list-evaluators --region $AWS_REGION \
    --query "evaluators[?evaluatorType=='Custom'].evaluatorId | [0]" --output text)
fi
echo "Using custom evaluator: $CUSTOM_ID"
```

**6c. Fetch the session's spans.** `evaluate` scores real span data, so pull this session's spans out of `aws/spans` and shape them with `jq`:

```bash
echo "Session: $SESSION_ID"
START=$(( ($(date +%s) - 3600) * 1000 ))

aws logs filter-log-events --region $AWS_REGION --log-group-name "aws/spans" \
  --start-time "$START" --max-items 300 --query 'events[].message' --output json \
  | jq --arg s "$SESSION_ID" \
    '{ sessionSpans: [ .[] | fromjson | select(.attributes."session.id" == $s) ] }' \
  > /tmp/eval_input.json

echo "spans collected: $(jq '.sessionSpans | length' /tmp/eval_input.json)"
TRACE_ID=$(jq -r '.sessionSpans[0].traceId' /tmp/eval_input.json)
echo "trace: $TRACE_ID"
```

If `spans collected` is 0, the spans have not finished indexing. Wait 60 to 90 seconds after chatting and re-run.

**6d. Run each evaluator.** `evaluate` takes one evaluator per call, so loop over the three:

```bash
for E in "Builtin.Correctness" "Builtin.Helpfulness" "$CUSTOM_ID"; do
  aws bedrock-agentcore evaluate --region $AWS_REGION \
    --evaluator-id "$E" \
    --evaluation-input file:///tmp/eval_input.json \
    --evaluation-target "{\"traceIds\":[\"$TRACE_ID\"]}" \
    --query 'evaluationResults[0].{evaluator:evaluatorName,score:value,label:label,reason:explanation}' \
    --output json
done
```

**6e. Read the scores.** Each call returns a score, a label, and the judge's reasoning. Your values will vary. A run against a shipped-order conversation looks like this:

| Evaluator | Score | Reasoning |
|---|---|---|
| Builtin.Correctness | 1.0 (Perfectly Correct) | Every factual claim matches the tool output |
| Builtin.Helpfulness | 1.0 (Above And Beyond) | Answers where the order is, with the details the customer needs |
| cs_accuracy | 1.0 (Grounded) | Called lookup_order, no invented details |

Accuracy scores well here because this agent emits tool-call spans tagged with `session.id`, so the judge can verify grounding directly. The self-managed 750 lab could not: its traces lack tool spans, so accuracy scored near zero there. Same judge methodology, richer traces, higher scores.

## What you built

Automated quality scoring on customer conversations with a managed judge instead of one wired inside Langfuse. You mixed two built-in evaluators with a custom retail-accuracy evaluator, ran them on demand from the CLI, and kept the Langfuse trace view intact by dual-exporting spans.

Compare the two tracks:

| | Self-managed (750 LLM-as-a-Judge) | Integrated (this module) |
|---|---|---|
| Judge | claude-sonnet-4-5 via LiteLLM, inside Langfuse | AgentCore Evaluations (managed) |
| Trace source | Langfuse | AgentCore Observability (dual-exported) |
| Evaluators | Custom + managed (Langfuse library) | Built-in + custom (cs_accuracy) |
| Levels | Trace | Span, trace, or session |
| Runs where | Langfuse UI | bedrock-agentcore API and CLI |

## What's next

Tear down the integrated workloads in the Cleanup lab.
</content>
