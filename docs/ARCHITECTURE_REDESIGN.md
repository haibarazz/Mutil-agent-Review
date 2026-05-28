# Architecture Redesign

## Why Rewrite

The legacy implementation is useful as a working prototype, but it binds the
core review flow to Coze runtime assumptions:

- environment variables are loaded through Coze workspace identity;
- graph service, logging, streaming, and node execution depend on Coze helpers;
- review nodes call Coze `LLMClient`, `SearchClient`, and `FetchClient`
  directly;
- document parsing is a generic `FileOps` utility rather than a paper-focused
  parser;
- future frontend needs stable run, artifact, and status APIs.

The rewrite keeps the domain behavior and replaces the runtime foundation.

## Migration Boundary

Legacy files live in `reference/legacy-coze-review/`.

Already migrated from legacy:

- legacy prompt content to Markdown files in `prompts/`;
- venue profile assets from `CCFA/` and `ut d/` to `venues/ccfa/` and
  `venues/utd_ft50/`;
- review role behavior into `src/graphs/review_nodes.py`.

Still use legacy as reference for:

- workflow order from `src/graphs/graph.py`;
- state and output vocabulary from `src/graphs/state.py`;
- mock paper and screenshots from `assets/`.

Replace:

- Coze runtime context;
- Coze LLM/search/fetch clients;
- `COZE_WORKSPACE_PATH` config loading;
- generic `FileOps` as the central paper parser;
- API shape built around Coze graph service.

## Target Architecture

```text
src/
  core/        review models, prompt loading, venue profile loading
  ports/       LLM, parser, search, fetch, storage contracts
  infra/       parser, LLM, storage, search, and settings adapters
  graphs/
    state.py   graph state contract
    graph.py   active LangGraph topology
    nodes/     clean node functions mirroring the original Coze graph
  services/    application wrapper around LangGraph and artifacts
  api/         FastAPI backend boundary for future frontend
  cli.py       local developer entrypoint
frontend/      frontend placeholder
```

The dependency direction is strict:

```text
api/cli -> services -> src/graphs -> core + ports
infra -> ports + core
core -> standard library only
```

Review nodes must not import provider SDKs directly. They receive capability
objects through ports.

## Runtime Model

Each review run produces a stable artifact folder:

```text
data/runs/{run_id}/
  request.json
  parsed_paper.json
  venue_profile.json
  reviewer_reports.json
  final_decision.json
  final_report.md
```

This makes CLI, API, and future frontend read the same durable state.

## Environment

Use local `.env` values, loaded by our own settings module:

```text
LLM_PROVIDER=mock | openai_compatible | router
LLM_BASE_URL=
LLM_API_KEY=
LLM_DEFAULT_MODEL=
LLM_CONFIG_PATH=configs/llm.yaml
PARSER_BACKEND=auto
MINERU_API_TOKEN=
MINERU_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm
MINERU_TIMEOUT_SEC=300
MINERU_POLL_INTERVAL_SEC=3
MINERU_REQUEST_TIMEOUT_SEC=30
DATA_DIR=./data
LEGACY_REFERENCE_DIR=reference/legacy-coze-review
PROMPTS_DIR=prompts
VENUES_DIR=venues
```

Default mode is `mock` so local smoke tests do not require external services.
For multi-provider runs, use `LLM_PROVIDER=router`; prompt Markdown files keep
only the model id, and `configs/llm.yaml` maps that model id to a provider plus
per-prompt call parameters.

## Parser Plan

Phase 1 parser:

- `.txt`, `.md`, `.tex`: direct text extraction;
- `.pdf`: MinerU standard API when `MINERU_API_TOKEN` is configured, then
  PyMuPDF fallback;
- `.docx`: python-docx when installed.

Phase 2 parser:

- preserve page, section, table, and figure anchors for reviewer evidence;
- make parser output frontend-highlightable spans.

## Review Flow

Submission preparation happens outside LangGraph:

```text
paper file + domain + venue collection + venue code + review mode
  -> validate submission
  -> create ReviewRequest
  -> invoke LangGraph from doc_parse
```

Phase 1 keeps the legacy flow shape:

```text
parse -> content_check -> venue_profile -> field_analysis
      -> optional SE/AE screen -> reviewer1/reviewer2/reviewer3/DA -> AE final
```

The active implementation now runs through `src.graphs.graph.main_graph` and
reads Markdown prompts for content check, journal requirement extraction, field
analysis, SE, AE, reviewers, Devil's Advocate, and AE final. `mock` LLM mode
keeps this path runnable without API keys; provider-backed behavior should be
hardened next.

## API Plan

Frontend-facing endpoints should stay close to the product workflow:

```text
GET  /health
GET  /api/venues
POST /api/reviews
GET  /api/reviews/{run_id}
GET  /api/reviews/{run_id}/report
```

The first `POST /api/reviews` can run synchronously. Later it should become an
async job with SSE progress events.

## Milestones

### M1: Framework Bootstrap

- archive legacy implementation;
- create local settings, ports, adapters, domain models;
- support CLI `doctor`, `parse`, `review`, and `venues`;
- write smoke tests for parser, venue loading, and workflow.

### M2: Real Tooling

- implement OpenAI-compatible LLM adapter;
- improve JSON extraction and timeout errors;
- implement paper-focused parser anchors;
- add real search/fetch adapters.

### M3: Prompt Parity

- harden provider-backed behavior for migrated prompts;
- add schema validation for SE/AE/reviewer/DA node outputs;
- compare output against legacy mock paper.

### M4: Product API

- persist run metadata;
- add async run status;
- expose report and artifacts for frontend;
- add API contract tests.

### M5: Frontend

- upload and configuration screen;
- progress timeline;
- report reader;
- run history.
