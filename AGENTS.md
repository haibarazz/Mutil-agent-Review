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
- Do not run `git push` unless the user explicitly asks to push or upload to
  GitHub in the current turn. During active development, local commits are okay
  when useful, but remote publishing needs explicit permission every time.

## GitHub Development Flow

默认按照 Pull Request 流程开发，帮助用户熟悉真实项目协作节奏：

1. 从 `main` 开一个开发分支，分支名默认使用 `codex/` 前缀。
2. 在开发分支完成代码或文档修改。
3. 本地提交 commit，commit 信息要简洁说明本次改动。
4. 只有在用户当前明确允许时，才 push 开发分支到 GitHub。
5. push 后创建 Pull Request，请求把开发分支 merge 到 `main`。
6. 用户 review / approve Pull Request。
7. 用户确认后再 merge Pull Request 到 `main`。
8. merge 后本地切回 `main`，同步远端 `main`，再删除已合并的开发分支。

说明：Pull Request 就是申请把当前开发分支合并到 `main`。除非用户明确要求，
不要跳过 PR 直接把开发分支内容推到 `main`。

## Verification

Run the lightweight checks before claiming a framework change is complete:

```bash
python -m unittest discover tests
python -m src.cli doctor
```
