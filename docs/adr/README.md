# Architecture Decision Records

An ADR records one significant design decision: the situation that forced it, what was decided, and what
follows from it. ADRs are short and immutable once accepted; a later decision that changes course gets a
new ADR that supersedes the old one (and the old one's status is updated to point to it).

Add an ADR when a change affects the architecture, a public contract (CLI, API, `run.json`, config keys)
or how results are judged or evaluated. Number sequentially (`NNNN-short-title.md`) and add it to the list
below.

## Status values

- **Proposed**: under discussion, not yet implemented.
- **Accepted**: decided and reflected in the code.
- **Deprecated**: no longer applies, without a direct replacement.
- **Superseded by NNNN**: replaced by a later ADR.

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Deprecated | Superseded by NNNN
- Date: YYYY-MM

## Context
What problem or force makes a decision necessary? Facts, constraints, evidence.

## Decision
What we do, stated plainly.

## Consequences
What becomes easier or harder; costs, risks, follow-ups.
```

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-llm-designs-kernel-judges.md) | The LLM designs, the geometry kernel judges | Accepted |
| [0002](0002-own-agent-loop.md) | A small own agent loop instead of an agent framework | Accepted |
| [0003](0003-disputable-l2-assertions.md) | L2 assertions are LLM-derived and can be disputed | Accepted |
| [0004](0004-l3-feedback-with-constraints.md) | L3 violations are fed back with requirement-derived constraints | Accepted |
| [0005](0005-ground-truth-from-reference-solids.md) | Evaluation ground truth comes from reference solids | Accepted |
