# 0004. L3 violations are fed back with requirement-derived constraints

- Status: Accepted
- Date: 2026-10

## Context

The DFM task set (12 tasks whose literal reading violates at least one DFM rule) showed that L3 feedback
reduces DFM errors but pulls the part away from the request. In the first run, final pass dropped from 97%
(config A) to 81% (config C): to satisfy DFM rules the model thickened walls and moved holes.

## Decision

When L3 is part of the feedback (config C), the repair prompt also lists the requirement-derived
constraints that must not change: bounding box, hole count, hole diameters and hole positions, built by
`_constraints_text(spec)` in `core/agent`. The prompt says to keep a DFM warning rather than violate the
request (`prompts.fix_user`).

## Consequences

Re-run of all three configs on the DFM set (numbers as reported in the README):

| | First run | After this change |
|---|---|---|
| Final pass, A vs C | 97% vs 81% (gap 16 points) | 92% vs 89% (gap 3 points) |
| Disputes (C) | 61 | 46 |
| Final L3 errors (C, mean) | 1.69 | 1.67 |

- The fidelity gap shrank from 16 to 3 points while the DFM gain was kept (residual errors 1.69 -> 1.67,
  versus 2.36 without L3 feedback in the re-run).
- **Caveat:** config A itself moved from 97% to 92% between the two runs (same tasks, same model name), so
  run-to-run noise is several points; the intervals overlap and the improvement is a trend, not a
  significant result. Small sample (36 per cell); tasks written by the authors; one model.
- L3 feedback still costs about 2.5x the tokens and does not reach zero DFM errors; it can still pull the
  part away from the request, just less.
- The previous run is kept in `eval/results_dfm/previous/`.
