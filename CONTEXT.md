# Domain Context

## Product

Paper Review Agent simulates a journal or conference review workflow for an
uploaded manuscript. It should help authors understand desk-reject risk, reviewer
concerns, likely rebuttal pressure, and concrete revision paths.

## Domain Glossary

- Paper: the uploaded manuscript after parsing.
- Venue profile: target journal or conference expectations, loaded from CCFA,
  UTD24, FT50, or manual input.
- SE: Senior Editor, responsible for initial desk-screening.
- AE: Associate Editor, responsible for rubric creation, external review
  routing, and final decision.
- Reviewer 1: methodology reviewer.
- Reviewer 2: field and contribution reviewer.
- Reviewer 3: cross-disciplinary and presentation reviewer.
- Devil's Advocate: adversarial reviewer that challenges the strongest claims.
- Part1: the formal review report: summary, strengths, weaknesses, rating.
- Part2: strategic advice: root causes, salvageability, and action guide.
- R&R matrix: revision-and-response traceability matrix connecting reviewer
  concerns to required author actions.

## Active Rewrite Goal

The active codebase should preserve the review-domain behavior while removing
the Coze-specific runtime. Environment, parser, LLM, search, storage, and future
frontend concerns should be controlled by our own code.

The active review topology lives in `src/graphs/graph.py`, with nodes in
`src/graphs/nodes/`. This intentionally mirrors the original project shape while
removing Coze runtime dependencies.

Submission configuration happens before LangGraph. The product-facing venue
selection is `CS -> CCFA/CCFB/CCFC -> venue_code` or
`IS -> FT50/UTD24 -> venue_code`; after validation the graph still starts at
`doc_parse` with `paper_path`, `review_mode`, and `venue_code`.

## Legacy Reference

Use `reference/legacy-coze-review/` for:

- LangGraph workflow sequence.
- Existing graph/state naming.
- Screenshots and mock inputs under `assets/`.

Do not edit legacy files unless the user explicitly asks to update the reference.

Active Markdown prompts live in `prompts/`. Active venue profiles live in `venues/`.
