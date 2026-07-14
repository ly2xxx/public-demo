# langgraph_ollama × md-mcp — Structure & Call Flow (as the code actually is)

> Drawn from source audit 14 Jul 2026: `app.py`, `rag_research_chatbot.py`, `tools/mcp_notes.py`, `tools/rag.py`, `telemetry.py` (langgraph_ollama) · `server.py`, `scanner.py`, `chunking.py`, `semantic.py`, `telemetry.py` (md_mcp).
> Use: your own deep-dive reference if Ross asks "so how does it actually work?" — every box below exists in code.

## 1 · Structure (static view)

```mermaid
flowchart TB
    subgraph HOST["Host machine"]
        subgraph APP["langgraph_ollama — Streamlit app (Python 3.12, uv)"]
            UI["Streamlit UI<br/>app.py"]
            GRAPH["LangGraph StateGraph<br/>entry: rag → conversation<br/>cond: msgs > 3 → summarize<br/>SqliteSaver checkpointer (in-mem)"]
            RAGNODE["local_rag node<br/>create_openai_tools_agent<br/>+ AgentExecutor"]
            RAGTOOL["rag_query tool<br/>tools/rag.py<br/>FAISS + OllamaEmbeddings<br/>(nomic-embed-text, local)"]
            MCPLOADER["load_md_mcp_tools<br/>tools/mcp_notes.py<br/>· module-level tool cache<br/>· 60s failure-retry throttle<br/>· sync-wraps async MCP tools<br/>· returns [] if unavailable"]
            TEL["telemetry.py (optional extra)<br/>OpenInference auto-instruments<br/>LangChain callbacks + custom metrics"]
        end

        OLLAMA["Ollama gateway :11434<br/>OLLAMA_MODEL=glm-5.2:cloud today<br/>(local Llama/Mistral = same API)"]

        subgraph MCP["md-mcp — Docker container (spawned on demand)"]
            FASTMCP["FastMCP server 'markdown-docs'<br/>stdio transport"]
            TOOLS3["tools: search_markdown ·<br/>list_files · rescan_folder"]
            SCAN["MarkdownScanner<br/>+ watchdog file watcher<br/>(cache invalidation)"]
            CHUNK["chunking + keyword search<br/>(semantic = optional extra,<br/>keyword fallback)"]
        end

        VOL["MD_MCP_FOLDER<br/>mounted at /data<br/>(read-only by design)"]

        subgraph OBS["Observability stack — docker compose"]
            COLL["OTel Collector<br/>:4317 gRPC OTLP"]
            TEMPO["Tempo<br/>traces :3200"]
            PROM["Prometheus<br/>metrics :9090"]
            GRAF["Grafana<br/>dashboards :3001"]
        end
    end

    CLOUD["Ollama cloud models<br/>(glm-5.2 / gpt-oss / minimax)"]

    UI --> GRAPH
    GRAPH --> RAGNODE
    RAGNODE -->|"tool 1"| RAGTOOL
    RAGNODE -->|"tools 2..n"| MCPLOADER
    MCPLOADER -->|"docker run -i --rm<br/>-e MD_TRANSPORT=stdio<br/>-v folder:/data"| FASTMCP
    FASTMCP --> TOOLS3
    TOOLS3 --> SCAN
    SCAN --> CHUNK
    VOL -.-> SCAN
    RAGNODE -->|"LLM + tool-calling"| OLLAMA
    OLLAMA -.->|":cloud models proxy"| CLOUD
    TEL -.->|"OTLP spans + metrics"| COLL
    COLL --> TEMPO
    COLL --> PROM
    TEMPO --> GRAF
    PROM --> GRAF

    classDef app fill:#3776ab,color:#fff,stroke:#2b5b84
    classDef mcp fill:#742774,color:#fff,stroke:#5c1f5c
    classDef obs fill:#b07a00,color:#fff,stroke:#8a6000
    classDef ext fill:#5a5a5a,color:#fff,stroke:#3d3d3d

    class UI,GRAPH,RAGNODE,RAGTOOL,MCPLOADER,TEL app
    class FASTMCP,TOOLS3,SCAN,CHUNK,VOL mcp
    class COLL,TEMPO,PROM,GRAF obs
    class OLLAMA,CLOUD ext
```

## 2 · Call flow (one query, dynamic view)

```mermaid
sequenceDiagram
    autonumber
    participant U as User<br/>(Streamlit UI)
    participant G as LangGraph<br/>rag node
    participant L as load_md_mcp_tools<br/>(mcp_notes.py)
    participant D as md-mcp container<br/>(docker stdio)
    participant A as AgentExecutor<br/>(openai-tools agent)
    participant O as Ollama :11434<br/>(glm-5.2:cloud)
    participant T as OTel Collector<br/>→ Tempo/Prom/Grafana

    U->>G: "Search my notes for Mercury — what is it?"
    G->>L: collect tools = [rag_query] + md-mcp tools
    alt first call this process
        L->>D: docker run -i --rm -v folder:/data (stdio)
        D-->>L: tool schemas: search_markdown, list_files, rescan_folder
        Note over L: sync-wrap + cache for process lifetime
    else cached / unavailable
        Note over L: return cached tools, or [] +<br/>retry at most once per 60s
    end
    G->>A: invoke agent with query + tools
    A->>O: chat completion (system prompt + tools schema)
    O-->>A: tool_call: search_markdown(query="Mercury")
    A->>D: call tool over stdio (asyncio.run via sync wrapper)
    D->>D: ensure_scanned → chunk → keyword match<br/>(watcher invalidates cache on file change)
    D-->>A: snippets + md:// source references
    A->>O: tool result → final generation
    O-->>A: grounded answer citing notes
    A-->>G: {"summary": answer}
    G->>G: conversation node (call_model)<br/>cond: >3 msgs → summarize node
    G-->>U: answer rendered in UI
    Note over G,T: OpenInference emits spans per graph node +<br/>LLM call (latency, token counts) → OTLP :4317
```

## 3 · Design details worth saying out loud (all true in code)

- **Graceful degradation everywhere:** no `MD_MCP_FOLDER` → `[]`, app unchanged; container missing → warn, `[]`, retry ≤1/min; OTel packages missing or collector down → telemetry is a no-op, never breaks the app.
- **The whole integration is one env var** — `MD_MCP_FOLDER=path`. The loader spawns `docker run --rm` per session (stdio), so there's no daemon to manage and nothing persists.
- **Caching at the right layers:** tool schemas cached per process (Streamlit reruns the script per interaction — discovery would otherwise round-trip every click); md-mcp caches its scan and invalidates via the file watcher.
- **Async/sync seam handled explicitly:** MCP adapter tools are async-only; the AgentExecutor path is sync — hence the `StructuredTool` sync wrapper running `asyncio.run` per call.
- **Security posture:** `/data` mount read-only (embeddings cache relocated via `MD_CACHE_DIR` to keep it so); md-mcp telemetry records call *shape* not content, and only activates when an OTLP endpoint is explicitly configured.
