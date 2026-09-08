# String Analysis API — System Design & Implementation Plan

## 1. Architecture & Module Layout
```text
├── src/string_analyzer/
│   ├── domain/        # Pure Python: protocols, dataclasses, analyzers (zero external deps)
│   │   ├── models.py  # AnalysisType enum, AnalysisResult, AnalysisRequest dataclasses
│   │   ├── protocol.py# AnalyzerStrategy Protocol (key, analyze(text) -> Any)
│   │   └── registry.py# Built-in analyzers (WordCount, CharCount, Frequency, ReadingTime) & registry
│   └── api/           # FastAPI adapter layer
│       ├── config.py  # Settings (max input size: default 1MB, log level) via pydantic-settings
│       ├── schemas.py # Pydantic v2 schemas (RawTextPayload, AnalysisResponse, ErrorResponse)
│       ├── routes.py  # Endpoints: POST /analyze (text/json) & POST /analyze/file (multipart .txt)
│       └── main.py    # FastAPI app, structured JSON logging middleware, exception handlers
├── tests/
│   ├── unit/          # Pure domain unit tests (WordCount, CharCount, Frequency, ReadingTime)
│   └── integration/   # FastAPI TestClient endpoint & validation tests
├── Dockerfile         # Multi-stage build with ghcr.io/astral-sh/uv:python3.12-bookworm-slim
└── pyproject.toml     # uv package configuration, dependencies, pytest settings
```

## 2. Domain Strategy Protocol
- **`AnalyzerStrategy` (Protocol)**: `key: AnalysisType` & `analyze(text: str) -> Any`
- **Core Analyzers**:
  - `WordCountAnalyzer`: Regex/whitespace-aware token count (`int`).
  - `CharacterCountAnalyzer`: Raw length and non-whitespace character count (`dict[str, int]`).
  - `FrequencyAnalyzer`: Case-normalized word frequency map (`dict[str, int]`).
  - `ReadingTimeAnalyzer`: Estimated reading duration at 200 WPM (`float` minutes/seconds).
- **Execution**: `AnalyzerRegistry` dynamically dispatches only the requested analyses in O(N).

---

## 3. Implementation Phases & Definition of Done (DoD)

### Phase 1: Domain Core & Strategy Analyzers
* **Target Files**:
  - `src/string_analyzer/domain/models.py`
  - `src/string_analyzer/domain/protocol.py`
  - `src/string_analyzer/domain/registry.py`
  - `tests/unit/test_analyzers.py`
* **Definition of Done (DoD)**:
  - All 4 analyzers (`WordCount`, `CharCount`, `Frequency`, `ReadingTime`) implement `AnalyzerStrategy`.
  - Zero external dependencies in `domain/` (pure standard library: `dataclasses`, `re`, `collections`, `typing`).
  - Comprehensive unit test suite covering: empty strings, whitespace-only, unicode/emojis, case folding, and unknown analyzer fallbacks.
  - **Coverage Target**: Minimum **85%** test coverage on all domain logic (`pytest --cov=string_analyzer.domain`).

### Phase 2: FastAPI Entrypoint, Boundary Validation & Docker Packaging
* **Target Files**:
  - `src/string_analyzer/api/config.py`
  - `src/string_analyzer/api/schemas.py`
  - `src/string_analyzer/api/routes.py`
  - `src/string_analyzer/api/main.py`
  - `tests/integration/test_api.py`
  - `Dockerfile`, `pyproject.toml`
* **Definition of Done (DoD)**:
  - `POST /api/v1/analyze` accepts raw string / JSON text with configurable byte-limit validation (default 1MB, returns `413 Payload Too Large`).
  - `POST /api/v1/analyze/file` handles `multipart/form-data` `.txt` file uploads with streaming byte-limit checks.
  - Dynamic analyzer selection via `?analyses=word_count,character_count,...` with 422 validation on invalid keys.
  - Structured JSON logging middleware (correlation ID, timestamp, payload size, duration) + `/healthz` probe.
  - Integration test suite (`TestClient`) verifying: 200 OK outputs, 413 limit violations, 422 bad queries, file upload flows.
  - Multi-stage `Dockerfile` with `uv` building an unprivileged container passing clean startup.
