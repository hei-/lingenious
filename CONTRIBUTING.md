# Contributing

Thanks for helping. Everything runs in Docker; no local CadQuery install is needed.

Orientation: [docs/architecture.md](docs/architecture.md) (modules and data flow), [docs/adr/](docs/adr/README.md) (design decisions), [AGENTS.md](AGENTS.md) (short conventions list).

## Dev loop

```bash
cp .env.example .env                       # only needed for runs that call the LLM
make setup                                 # builds lingenious:dev (the `dev` Dockerfile target: runtime + pytest/ruff)
make test                                  # pytest in the container
make lint                                  # ruff check + mypy
make cov                                   # pytest with coverage (terminal summary + coverage.xml)
scripts/run.sh demo "<requirement>"        # end-to-end run, results in out/demo/
```

`make help` lists everything else: `ui-install` / `ui-check` / `ui-build` for `web/ui` (Node 22), `web` (`docker compose up --build`, app at http://localhost:8000), `eval-dfm`, `landing-serve`.

Dependencies are declared in `pyproject.toml`; the Docker images install from the hash-pinned `requirements.lock` (runtime) and `requirements-dev.lock` (dev). After changing dependencies run `make lock` (needs [uv](https://docs.astral.sh/uv/)) and commit the lock files. The package is installable with `pip install -e .` (Python 3.10-3.12).

On slow networks, set `APT_MIRROR` / `PIP_INDEX_URL` to pass package mirrors to the image build. Rebuild after code changes (the image copies the tree). Please run the tests before opening a PR.

## Adding a DFM rule

1. In `core/checks/l3.py`, write a function decorated with `@rule("<rule_id>", "L3")` that returns a list of `Issue` (include measured values and a hint in the message).
2. Register it in `L3_RULES` in `core/checks/__init__.py` (and in the import line).
3. Add a default threshold in `core/checks/base.py` (and, if useful, a commented example in `config.yaml`).
4. Add tests in `tests/test_dfm_rules.py` (one case that triggers, one that does not).
5. Document it in [`docs/dfm-rules.md`](docs/dfm-rules.md).

**Threshold rule:** any new or changed threshold must state its source (standard, handbook, process engineer's input) or be labeled "rule of thumb" in the docs and code comment. Do not present unverified numbers as fact.

## Adding an eval task

1. Write the reference solid in `eval/refs/<id>.py` (DFM set: `eval/refs_dfm/`), following an existing file.
2. Add the task id, difficulty and text to `eval/tasks.py` (DFM set: `eval/tasks_dfm.py`).
3. Rebuild ground truth: `python -m eval.build_truth` (DFM set: `python -m eval.build_truth_dfm`), which rewrites `eval/truth.json` / `eval/truth_dfm.json` from the reference solids.
4. Run the tests: every reference solid must pass all checks; DFM-set tasks must violate at least one rule in their literal reading.

Do not edit results files by hand; regenerate them with `eval.runner` and `eval.report`, and keep interpretations honest (small samples, noise, single model).

## Code style

Plain, typed Python with short docstrings for non-obvious logic. `ruff check` (a conservative rule set, see `pyproject.toml`) and `mypy` (lenient baseline; modules with known errors are listed under `[[tool.mypy.overrides]]`, please shrink that list, never grow it) run in CI; `web/ui` runs `eslint` (`npm run lint`). `ruff format` is deliberately not enforced (it would reformat most of the tree). Keep diffs free of unrelated reformatting. Keep judgement logic deterministic: the LLM must not decide pass/fail.

## Pre-commit

```bash
pip install pre-commit && pre-commit install
```

Runs ruff, whitespace/EOF/yaml/json/large-file (800 kB) checks and `scripts/scan_secrets.py` (sk- keys, `DEEPSEEK_API_KEY=<value>`, Feishu tokens). Never commit `.env`.

## Releases

Versions follow SemVer, `0.x` while the API is unstable. The single source of truth is `version` in `pyproject.toml` (keep `web/ui/package.json` in step).

1. Move the `Unreleased` entries of `CHANGELOG.md` under a new `## [0.x.y] - YYYY-MM-DD` heading and bump `version` in `pyproject.toml`.
2. Merge to `main` with CI green (python, ui, docker-web, landing).
3. Tag and push: `git tag v0.x.y && git push origin v0.x.y`.
4. `.github/workflows/release.yml` builds `web/Dockerfile` and pushes `ghcr.io/<owner>/<repo>-web:{0.x.y,0.x,latest}` using the built-in `GITHUB_TOKEN` (no repository secrets; the image is build-only, nothing is deployed). Pre-release tags (`v0.2.0-rc1`) do not get `latest`.
5. Create the GitHub release from the tag, pasting the changelog section.

Dependabot (weekly) proposes pip, npm (`web/ui`), GitHub Actions and Docker updates; after merging pip updates run `make lock`.

## Security

The sandbox is not safe for untrusted code. Report vulnerabilities as described in [SECURITY.md](SECURITY.md).
