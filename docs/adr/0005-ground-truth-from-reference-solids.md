# 0005. Evaluation ground truth comes from reference solids

- Status: Accepted
- Date: 2026-10

## Context

The agent's own L2 checks use assertions the LLM derived from the requirement
([ADR 0003](0003-disputable-l2-assertions.md)). Grading the evaluation against that spec would let a
misreading pass ("matches what it thought you asked"), and disputes would make the score circular.
Hand-written expected values are error-prone and may be unsatisfiable.

## Decision

- Every task has a hand-written reference CadQuery script: `eval/refs/<id>.py` for the main set,
  `eval/refs_dfm/<id>.py` for the DFM set (the DFM-compliant reading; `*_naive.py` files hold the literal
  reading and are excluded from truth).
- `python -m eval.build_truth` / `python -m eval.build_truth_dfm` execute the references in the sandbox and
  derive the ground truth automatically (`derive()` in `eval/build_truth.py`): bounding box (tol 0.5 mm),
  hole count and diameters via `find_holes` (tol 0.15 mm), volume range ±3%. Results go to
  `eval/truth.json` / `eval/truth_dfm.json`.
- `eval.runner.grade` re-executes the agent's first-round and final scripts and checks L1 + L2 against
  this truth, independent of the LLM-parsed spec. L3 errors are counted separately with the default
  `PartSpec`.
- Tests check that every reference solid passes all checks and that each DFM task's literal reading
  violates at least one DFM rule.

## Consequences

- Scores do not depend on the LLM's interpretation, and disputes cannot inflate them.
- Truth is reproducible and cannot be unsatisfiable, since a passing solid exists.
- Truth covers only what `derive()` measures: hole positions and feature details beyond bbox, hole
  diameters and volume are not graded, and a different shape with the same measurements passes.
- The reference reading is the authors' interpretation of each task; the task sets are small (24 + 12).
