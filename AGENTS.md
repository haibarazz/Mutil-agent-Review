# Project Agent Guide

## Project

This repo is being rebuilt as a local-first multi-agent paper review system.
The legacy Coze implementation is archived in `reference/legacy-coze-review/`
and must be treated as reference material, not the active code path.

## Active Architecture

- Active graph package: `src/graphs/`
- Domain package: `src/core/`
- Infrastructure package: `src/infra/`
- API/CLI package: `src/api/` and `src/cli.py`
- Durable plan: `docs/ARCHITECTURE_REDESIGN.md`
- Domain context: `CONTEXT.md`
- Legacy reference: `reference/legacy-coze-review/`
- Local artifacts: `data/runs/` (ignored)

## Engineering Rules

- Keep the review-domain logic independent from external SDKs.
- New LangGraph nodes should live under `src/graphs/nodes/`.
- Node business logic should depend on `src.ports.*` protocols, not
  concrete providers.
- Do not reintroduce Coze runtime dependencies into active code.
- Keep parser, LLM, search, fetch, storage, and venue loading replaceable through
  adapters.
- Preserve existing review concepts: SE, AE, Reviewer 1/2/3, Devil's Advocate,
  Part1 review report, Part2 strategic advice, R&R traceability matrix, and
  revision roadmap.
- Frontend-facing API contracts should be stable, small, and artifact-backed.
- The main review path must run through `src.graphs.graph.main_graph`.
- For now, prefer a CLI smoke path before adding UI work.
- When writing new code or changing non-obvious logic, prefer concise Chinese
  comments that explain intent, workflow boundaries, or tricky decisions. Avoid
  noisy comments that only restate obvious code.

## Verification

Run the lightweight checks before claiming a framework change is complete:

```bash
python -m unittest discover tests
python -m src.cli doctor
```
