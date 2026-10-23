# 0003. L2 assertions are LLM-derived and can be disputed

- Status: Accepted
- Date: 2026-10

## Context

L2 checks compare the solid with `PartSpec.assertions` (bounding box, hole count, hole diameters, hole
positions, volume range). These assertions are produced by the LLM when it parses the requirement, so they
can be wrong. In the evaluation, task `m2` got the Y extent of a U-bracket as 58 instead of 50. A
correct script then fails L2, and the repair step would "fix" correct dimensions to satisfy a wrong
assertion.

## Decision

- The repair prompt (`prompts.fix_user`) includes the user's original requirement and explains that L2
  assertions may be wrong.
- If an L2 violation contradicts the requirement, the script may add a comment
  `# ASSERTION_DISPUTE: <rule>` and keep its dimensions.
- `_apply_disputes` in `core/agent` downgrades errors of disputed rules to warnings and prefixes the message
  with "[脚本申诉,以原始需求为准]" (script dispute; the requirement prevails), so disputes are visible in
  `run.json`, `log.txt` and the UI.
- Only `bbox_match`, `hole_count`, `hole_diameter`, `hole_position` and `volume_range` are disputable
  (`DISPUTABLE`). L1 (geometry validity), `hole_breakout` and all L3 (DFM) rules cannot be disputed; a
  dispute comment naming them has no effect.
- The evaluation counts disputes per run (`disputes` column in `results.csv`).

## Consequences

- Wrong assertions no longer force the model to break correct dimensions.
- The dispute itself is an LLM judgement: a model can also dispute a correct assertion to escape an error.
  This is why disputes are logged and counted, and why evaluation grades against independent ground truth
  rather than the LLM's own assertions ([ADR 0005](0005-ground-truth-from-reference-solids.md)).
- Hole positions that the requirement does not determine are not asserted, so they are not checked.
- `modify()` clears assertions entirely, because a change request can legitimately alter dimensions.
