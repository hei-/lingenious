# 0002. A small own agent loop instead of an agent framework

- Status: Accepted
- Date: 2026-10

## Context

The control flow is fixed and short: parse, generate, then up to N rounds of execute, check, repair. There
is no open-ended tool selection, no memory and no multi-agent routing. Frameworks such as LangChain or
low-code platforms such as Dify add abstractions (chains, tool registries, hosted workflows) that this flow
does not need, and they make it harder to see exactly what is sent to the model, to replace the model in
tests, and to switch individual feedback channels on and off for evaluation.

## Decision

Write the loop directly in Python (`core/agent/__init__.py`, about 180 lines) on top of a thin
OpenAI-compatible client (`core/llm.py`, about 60 lines). Prompts are plain strings in
`core/agent/prompts.py`. The loop takes an optional `on_event` callback, which the web app uses for SSE
progress events.

Evaluation configurations are a parameter of the same loop, not separate pipelines:

```python
CONFIG_LEVELS = {"A": (), "B": ("L1", "L2"), "C": ("L1", "L2", "L3")}
```

## Consequences

- **Small and readable:** the whole agent fits in two files; every message sent to the model is visible.
- **Testable:** tests and the web app swap in a fake LLM (`web.server.jobs.make_llm` is monkeypatched in
  `tests/test_web_server.py`); dispute handling and constraint text are pure functions with unit tests.
- **Deterministic control:** the number of rounds, early stop on repeated failures, issue ordering and the
  8-issue cap are code, not model behaviour.
- **Comparable evaluation:** configs A/B/C differ only in which check levels feed back, so the CLI, web
  app and `eval.runner` exercise identical code.
- We maintain retries, JSON validation (one pydantic-error retry in `LLM.structured`) and provider
  plumbing ourselves. Non-OpenAI-compatible providers need a small adapter class
  ([architecture.md](../architecture.md#extension-points)). There is no response cache or tracing beyond
  token counts in `run.json`.
