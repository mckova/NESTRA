---
name: nestra
description: Route a question through the installed NESTRA evidence layer and report its verified evidence, route, and token usage. Use when the user invokes NESTRA or asks for retrieval-first, accuracy-guarded inference.
---

# NESTRA

Use the installed `nestra` CLI. Do not simulate NESTRA routing.

1. Treat the user's text after the invocation as the question.
2. Run `nestra list`. If it returns one project, use it. If it returns several, prefer an exact current-directory-name match; otherwise ask the user to choose. If it returns none, explain that trusted JSON documents must first be added with `nestra ingest`.
3. Run `nestra query --project "<id>" --question "<question>" --mode auto`.
4. Report the answer; when `answer` is null, present the returned evidence without inventing a synthesis. Include `route`, `status`, `verified`, citations, model calls, total tokens, and latency.
5. If the result is blocked or `needs_review`, report that outcome. Never bypass NESTRA silently, expose credentials, or claim that the host AI CLI used zero tokens.
