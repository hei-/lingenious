"""CLI: python -m core.modify_cli --script part.py --run-json run.json --change "立板厚度改成4mm" --out DIR

Rebuilds the previous RunResult from part.py + run.json, then runs agent.modify and saves like core.cli."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


from core import agent
from core.config import load_config
from core.cli import _report
from core.llm import LLM
from core.models import PartSpec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--run-json", required=True)
    ap.add_argument("--change", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="C", choices=["A", "B", "C"])
    ap.add_argument("--cfg", default="config.yaml")
    ap.add_argument("--version", type=int, default=2, help="仅用于报告标题")
    a = ap.parse_args(argv)

    prev_run = json.loads(Path(a.run_json).read_text())
    spec = PartSpec(**prev_run["spec"])
    # only len(rounds) matters to agent.modify (round numbering continues)
    rounds = [agent.Round(r.get("n", i + 1), "", [], r.get("seconds", 0.0))
              for i, r in enumerate(prev_run.get("rounds") or [])]
    prev = agent.RunResult(status="success", spec=spec, code=Path(a.script).read_text(), rounds=rounds)

    cfg = load_config(a.cfg)
    llm = LLM(cfg)
    out = Path(a.out)
    res = agent.modify(llm, prev, a.change, cfg, out, a.config)
    _report(res, out, a.version)
    return 0 if res.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
