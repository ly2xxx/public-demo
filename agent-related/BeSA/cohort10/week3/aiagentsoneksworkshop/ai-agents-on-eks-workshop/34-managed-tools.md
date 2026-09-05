# Managed Capabilities (Browser + Code Interpreter)

Source: https://catalog.workshops.aws/ai-agents-on-eks/en-US/30-integrated-infrastructure/400-managed-tools

## At a glance

- **Goal:** Give the agent two managed AgentCore runtimes, Code Interpreter for sandboxed Python and Browser for live web pages.
- **Prerequisites:** The Agents using Strands with Bedrock lab

In this module, you'll give the agent two Amazon Bedrock AgentCore managed runtimes:

- **Code Interpreter:** sandboxed Python for calculations, data work, or quick reports
- **Browser:** sandboxed headless browser for fetching public web pages

Both fit the same spot as MCP in the self-managed Agent Tool Access (MCP) lab, but for code you don't want running anywhere near your pods. The model plane is unchanged, same `OpenAIModel` → LiteLLM → Nova.

## Step 1: Confirm the tool resources

```bash
kubectl get configmap agent-tools -n agents -o yaml
```

You should see `AGENTCORE_BROWSER_ID` and `AGENTCORE_CODE_INTERPRETER_ID`. The agent ServiceAccount already has `StartBrowserSession` / `StartCodeInterpreterSession` scoped to these ARNs.

## Step 2: Code walkthrough

```bash
cd ~/environment/modules/30-integrated/400-managed-tools/customer-agent
```

This module introduces a new file, `sandbox_tools.py`, which defines two tools using the `@tool` decorator. The `agent.py` file registers both tools alongside the existing `lookup_order` tool.

**sandbox_tools.py — run_python:**

```python
@tool
@observe(name="sandbox.run_python")
def run_python(code: str) -> str:
    """Execute Python code in a sandboxed AgentCore code interpreter and return stdout.

    Use this for calculations, data processing, or generating small reports.
    The sandbox has no access to internal AWS services.
    """
    session = _client.start_code_interpreter_session(
        codeInterpreterIdentifier=CODE_INTERPRETER_ID,
        sessionTimeoutSeconds=300,
    )
    session_id = session["sessionId"]
    try:
        resp = _client.invoke_code_interpreter(
            codeInterpreterIdentifier=CODE_INTERPRETER_ID,
            sessionId=session_id,
            name="executeCode",
            arguments={"language": "python", "code": code},
        )
        # ... read back stdout chunks ...
    finally:
        _client.stop_code_interpreter_session(
            codeInterpreterIdentifier=CODE_INTERPRETER_ID, sessionId=session_id)
```

- Three-step shape: `start_*_session` → `invoke` → `stop_*_session` in `finally`
- One session per call. This is clearer for the workshop. Production would cache sessions per agent or conversation.
- `@observe` stacks underneath `@tool` so Langfuse captures the code that was executed as span input and the stdout that came back as span output. Otherwise you'd see the tool call happen but not what ran inside the sandbox.
- `fetch_webpage` follows the same pattern with `BrowserClient` (from `bedrock-agentcore-starter-toolkit`) handling the Chrome DevTools Protocol WebSocket. You could wrangle the socket yourself, but life is short.

## Step 3: Deploy (image already built)

`k8s.yaml` mounts two ConfigMaps now: `agent-config` (memory + Langfuse) and `agent-tools` (sandbox IDs). The `customer-agent:agentcore-tools` image was pre-built and pushed to ECR during provisioning:

```bash
cd ~/environment/modules/30-integrated/400-managed-tools/customer-agent
envsubst < k8s.yaml | kubectl apply -f -
kubectl rollout status deployment/customer-agent -n agents --timeout=180s
```

## Step 4: Chat — exercise both tools

Open the chat UI, pick **Customer Agent (Integrated GenAI)**.

Test `run_python` — ask a question that needs arithmetic:

- "I want to total up what I spent on orders ORD-12345 and ORD-67890."

The agent should call `lookup_order` twice, then `run_python` with the arithmetic, then answer in natural language.

Test `fetch_webpage`:

- "compare the price of the mouse I bought with this one from Amazon - https://www.amazon.com/AmazonBasics-Wireless-Computer-Mouse-Receiver/dp/B005EJH6Z4"

Browser sessions take longer to start than Code Interpreter ones (fresh isolated browser every time). The latency is the price of isolation.

## Step 5: Inspect the traces

In Langfuse, you'll see `run_python` and `fetch_webpage` spans with:

- Tool input (code snippet or URL)
- Tool output (stdout or page text)
- Latency: usually dominated by session startup, not the actual work

Expand the `sandbox.run_python` span in the trace tree. The right panel displays two key details: the exact Python code that the model generated (Input) and the stdout returned by the sandbox (Output). The `@observe` decorator captures this level of detail. By comparison, the Strands `run_python` tool span next to it only records that the tool was invoked. It does not capture the code or its output.

The `sandbox.fetch_webpage` span follows the same pattern. The Input shows the URL the model requested, and the Output contains the scraped text that the AgentCore browser returned through CDP. This visibility is especially useful for identifying pages where the rendered content is primarily JavaScript and the agent received an empty shell instead of meaningful text.

## What you changed

- Added `sandbox_tools.py`
- Registered two more tools. Agent logic didn't move; it still sees tools, not infrastructure.
- Mounted a second ConfigMap so tool IDs land in the pod's env

## What's next

One agent, three tools. Time to split it into specialists. Same A2A pattern as the self-managed Multi-Agent A2A lab, but every specialist now runs on Bedrock + AgentCore.
</content>
