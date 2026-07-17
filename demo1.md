# An AI Engineering Journey - [github.com/ly2xxx/public-demo/blob/main/demo.md](https://github.com/ly2xxx/public-demo/blob/main/demo.md)

---

## [2023: RAG Chatbot](https://github.com/ly2xxx/langgraph_ollama/blob/main/tools/rag.py)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2023-rag-right.png" style="height: 400px; width: auto;">
</div>

---

## [2024: Multi-Agent Flows](https://github.com/ly2xxx/langgraph_ollama/blob/main/rag_research_chatbot.py)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2024-agent-right.png" style="height: 400px; width: auto;">
</div>

---

## [2025: Open Tool Standard (MCP)](https://github.com/ly2xxx/md-mcp)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2025-mcp-right.png" style="height: 400px; width: auto;">
</div>

---

## [2026: Observability](https://github.com/ly2xxx/langgraph_ollama/blob/main/IMPLEMENTATION_GUIDE.md)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2026-obs-right.png" style="height: 400px; width: auto;">
</div>

---

## [2026: Observability Dashboards](https://github.com/ly2xxx/langgraph_ollama/blob/main/docker-compose.observability.yml)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2026-obs2-right.png" style="height: 400px; width: auto;">
</div>

---

## [2026: Evaluation & BDD](https://github.com/ly2xxx/md-mcp/blob/feature/otel/sample-client/PYTEST-BDD.md)

<div style="display: flex; gap: 0; align-items: stretch;">
  <img src="common-left.png" style="height: 400px; width: auto;">
  <img src="2026-eval-right.png" style="height: 400px; width: auto;">
</div>


## 1 · Structure (static view)

```mermaid
flowchart TB
    subgraph HOST["Host machine"]
        subgraph APP["langgraph_ollama — Streamlit app (Python 3.12, uv)"]
            UI["Streamlit UI<br/>app.py"]
            GRAPH["LangGraph StateGraph<br/>entry: rag → conversation<br/>cond: msgs &gt; 3 → summarize<br/>SqliteSaver checkpointer (in-mem)"]
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
    RAGNODE -->|tool 1| RAGTOOL
    RAGNODE -->|tools 2..n| MCPLOADER
    MCPLOADER -->|docker run -i --rm<br/>-e MD_TRANSPORT=stdio<br/>-v folder:/data| FASTMCP
    FASTMCP --> TOOLS3
    TOOLS3 --> SCAN
    SCAN --> CHUNK
    VOL -.-> SCAN
    RAGNODE -->|LLM + tool-calling| OLLAMA
    OLLAMA -.->|:cloud models proxy| CLOUD
    TEL -.->|OTLP spans + metrics| COLL
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

---
