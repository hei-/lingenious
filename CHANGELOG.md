# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may break).

## [Unreleased]

## [0.1.0] - 2026-10-23

### Added
- Core agent loop: requirement -> spec -> CadQuery script -> deterministic checks -> repair (up to 4 rounds), plus follow-up edits that modify the previous script.
- Deterministic judge in `core/checks`: geometry validity (L1), spec assertions (L2) and DFM rules (L3), with measured values and hints fed back to the LLM.
- Sandboxed script execution, STEP export, shaded render and a three-view engineering drawing (hidden-line removal, sections, dimensions, DXF).
- Web app (FastAPI + React/three.js UI) with run history, 3D viewer, version compare and examples; Docker image for it, bound to localhost.
- Feishu Bitable adapter, evaluation harness (`eval/`, general and DFM task sets, reference solids, report generation).
- Engineering baseline: `pyproject.toml` (version 0.1.0), hash-pinned `requirements.lock` / `requirements-dev.lock`, Dockerfile `runtime` / `dev` targets, Makefile, ruff (check only), mypy with a lenient baseline, pytest-cov, ESLint for `web/ui`, pre-commit (including a simple secret scan).
- CI (GitHub Actions): python tests + lint + type check + coverage, UI typecheck/tests/lint/build, web image build with smoke test, landing page checks and GitHub Pages deploy; release workflow publishing the web image to GHCR on `v*` tags.
- Project files: CONTRIBUTING (incl. release process), issue and PR templates, CODEOWNERS (placeholder owner), Dependabot config, SECURITY policy, bilingual docs (en / zh-CN).

### Changed
- L3 repair prompt now carries the requirement-derived constraints (bounding box, hole count, diameters, positions) that must not change. DFM set re-run: the final-pass gap between config A and C shrank from 16 to 3 points (within noise); previous results kept in `eval/results_dfm/previous/`.
- Documentation restructured for open source: early planning notes removed; `docs/architecture.md` (as implemented) and `docs/adr/` (5 decision records) added; Feishu Bitable schema moved to `adapters/feishu_bitable/README.md`; remaining docs renamed without numbers (`dfm-rules.md`, `web-app.md`, `configuration.md`) and indexed by audience in `docs/README.md`; `AGENTS.md` added; `CLAUDE.local.md` / `AGENTS.local.md` git-ignored.

### Fixed
- Examples (`examples/`) and landing-page replay data regenerated with the current agent (3 runs per request, one published unedited): bracket v1 now shows L2 and L3 repairs (missing Ø20 wall hole, sharp internal corner) over 3 rounds; v2 records the spec update.
- Follow-up edits are dimension-checked again: `modify()` used to clear the L2 assertions, so "make the wall 4 mm" was never verified. It now updates the spec for the change (`update_spec`) and checks the new version against the updated assertions; on a failed update it falls back to L1 + L3 and records that in `defaults_used`.
- Spec parsing no longer stops with "need info" when only hole positions, fillets, chamfers or hole depth are unspecified: the prompt forbids listing them as missing and `parse_spec` moves any such item to `defaults_used`. U-bracket example request: 5/10 -> 0/10 false "need info"; underspecified requests still ask (10/10).

### Known gaps
- Thresholds of DFM rules are partly rules of thumb pending process-engineering review (see `docs/dfm-rules.md`).
- The sandbox is not safe for untrusted code (see SECURITY.md).

[Unreleased]: https://github.com/hei-/lingenious/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hei-/lingenious/releases/tag/v0.1.0
