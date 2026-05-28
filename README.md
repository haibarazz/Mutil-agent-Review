# Paper Review Agent

Local-first rewrite of the multi-agent paper review system.

The previous Coze/Vibe implementation has been archived under
`reference/legacy-coze-review/`. Treat it as a reference for workflow shape,
prompt wording, venue profiles, and UI screenshots. New development happens in
the active `src/` package.

## Current Shape

- LangGraph-first Python framework with a CLI and future FastAPI frontend boundary.
- Local `.env` configuration instead of Coze workspace variables.
- Ports and adapters for LLM, search, fetch, parser, venue profiles, and storage.
- Multi-provider LLM routing through `configs/llm.yaml`.
- Local artifact storage under `data/runs/`.
- Review prompts are Markdown files under `prompts/`; prompt frontmatter only
  declares the prompt name and model id.
- Venue selection is organized as CS/CCFA and IS/FT50/UTD24 before entering LangGraph.
- Venue profiles are active under `venues/ccfa/` and `venues/utd_ft50/`.

## Quick Start

```bash
uv venv
uv sync
cp .env.example .env
python -m src.cli doctor
python -m src.cli venue-catalog
python -m src.cli review paper.md --mode QUICK_REVIEW --venue-domain CS --venue-collection CCFA --venue-code AAAI
```

The default `LLM_PROVIDER=mock` makes the workflow runnable without API keys.
Switch to `router` after filling provider credentials in `.env`. The router
uses `configs/llm.yaml` to map prompt model ids to Doubao, DeepSeek, Kimi, GLM,
or other OpenAI-compatible providers.

## Important Paths

- `docs/ARCHITECTURE_REDESIGN.md`: full rewrite plan.
- `src/graphs/state.py`: graph state contract.
- `src/graphs/graph.py`: active LangGraph topology.
- `src/graphs/nodes/`: active node functions mirroring the original workflow.
- `src/graphs/review_nodes.py`: provider-free node business logic.
- `src/core/`: review-domain models, prompts, and venue profiles.
- `src/ports/`: tool contracts.
- `src/infra/`: parser, LLM, storage, search, and settings adapters.
- `configs/llm.yaml`: model registry and per-prompt LLM call parameters.
- `src/services/`: application service wrapper around LangGraph.
- `src/api/`: backend boundary for the future frontend.
- `src/cli.py`: local command-line entrypoint.
- `frontend/`: frontend placeholder.
- `reference/legacy-coze-review/`: frozen reference implementation.
- `prompts/`: active Markdown prompt files.
- `venues/`: active venue profiles migrated from the legacy workflow.
