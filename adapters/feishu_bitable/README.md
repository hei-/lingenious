# Feishu Bitable adapter (optional)

> **Optional demo front-end.** Nothing in `core/`, the web app or the evaluation depends on it, and the
> web image does not include it. Use the [web app](../../docs/web-app.md) for normal use.

A Feishu (Lark) Bitable acts as a shared request sheet: one row per part request. A polling script picks up
new rows, runs the agent in Docker, and writes status, iteration log, DFM report and attachments back to
the same row. Filling the "修改要求" (change request) column of a passed row triggers a modification of the
previous version.

## Prerequisites

- `lark-cli` (the Feishu/Lark command-line client) installed and logged in **as yourself**:
  `lark-cli auth login --domain base,drive`. All calls run with `--as user`; no app ID, app secret or token
  is stored in the repo or read from the environment.
- Docker and the dev image (`make docker-dev` builds `lingenious:dev`; override with `LINGENIOUS_IMAGE`).
- `.env` in the repo root with the LLM key; it is passed to the container with `--env-file`.

## Usage

```bash
python3 adapters/feishu_bitable/setup_base.py     # create the Base, table and one demo row (idempotent)
python3 adapters/feishu_bitable/poll.py --once    # process pending rows once
python3 adapters/feishu_bitable/poll.py --interval 10   # keep polling (default every 10 s)
```

`setup_base.py` creates a Base named "CAD Agent 需求单" with a table "需求表" in your own account and
stores `base_token`, `table_id` and the Base URL in `out/bitable/state.json` (git-ignored). Run outputs
are kept under `out/bitable/<record_id>/v<n>/`.

## Files

| File | Role |
|---|---|
| `larkio.py` | Thin `lark-cli` subprocess wrapper; raises `LarkError`, never logs secrets |
| `logic.py` | Pure functions, no I/O: record parsing, trigger decision, DFM report text, field mapping (unit-tested in `tests/test_feishu_adapter.py`) |
| `setup_base.py` | Creates the Base and fields |
| `poll.py` | Polling loop; runs `core.cli` / `core.modify_cli` in a throw-away container (`docker create`, `cp`, `start -a`, `cp` out, `rm`) and writes results back |

## Table schema (需求表)

| Field | Type | Written by | Meaning |
|---|---|---|---|
| 需求描述 | text | user | Free-text requirement |
| 材料 | single select | user | 6061 / 7075 / 304 / 45#; passed as `--material` |
| 工艺 | single select | user | CNC 铣削 (stored, not passed to the agent) |
| 状态 | single select | user + system | 待处理 (pending) / 生成中 (running) / 已通过 (passed) / 需补充 (needs info) / 需人工 (needs a human) |
| 修改要求 | text | user | Change request for the passed version; cleared after processing |
| 需补充信息 | text | system | Missing information (`spec.missing`), `;`-separated |
| 迭代轮数 | number | system | Rounds, cumulative across versions |
| 迭代日志 | text | system | Per-round log; each modification appends a `—— v<n> 修改:… ——` header |
| DFM 报告 | text | system | Verdict plus passed / warning / violation lines per level (L0-L3) |
| 渲染图 | attachment | system | `render.png` |
| 工程图 | attachment | system | `drawing.pdf`, `drawing.dxf` |
| STEP | attachment | system | `part.step` |
| 参数化脚本 | attachment | system | `part.py` |
| 版本 | number | system | Version, +1 per modification |
| 更新时间 | datetime | system | Last write-back |

## Trigger and write-back rules (`logic.py`, `poll.py`)

- **New run:** `状态` = 待处理 and `需求描述` non-empty.
- **Modification:** `状态` = 已通过 and `修改要求` non-empty. Uses `out/bitable/<record_id>/v<版本>/` as the
  base, so the previous version must have been produced on the same machine.
- Before processing, `状态` is set to 生成中 so the row is not picked up twice.
- Status mapping from `run.json`: `success` -> 已通过, `need_info` -> 需补充, otherwise 需人工.
- Attachments are uploaded first, then all text fields are written in one `+record-batch-update`.
- A failed modification keeps the row at 已通过 (the previous version stays valid), appends the failure to
  the log and clears `修改要求`.
- Any exception writes 需人工 and the error to the log, so a row never stays at 生成中.

## Limitations

- Polling only (default 10 s, first 200 records); no event subscription.
- `lark-cli` attachment upload is append-only, so files accumulate per version with `v1_`, `v2_` prefixes.
- The DFM report's list of passed rules (`LEVEL_RULES` in `logic.py`) names only the original L2/L3 rules;
  violations of newer rules are still listed.
- Share the Base read-only for demos; a link with edit rights lets anyone trigger runs on your API key.
