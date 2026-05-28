# ADR 0001: Local-First Modular Monolith

## Status

Accepted.

## Context

The previous system proved the review workflow but tied core logic to Coze
runtime and provider-specific SDKs. The next version needs our own environment,
replaceable tools, and a frontend-ready backend.

## Decision

Build a local-first modular monolith in Python. Keep the review domain in
`src/core`, define external capabilities in `src/ports`, and
put concrete tool integrations in `src/infra`.

## Consequences

- CLI and API can share the same workflow.
- Mock adapters make tests and demos runnable without API keys.
- Parser, LLM, search, and storage can be replaced independently.
- Frontend work can start once artifact-backed API contracts stabilize.
