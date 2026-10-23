"""python -m eval.build_truth_dfm -> eval/truth_dfm.json (from the DFM-clean refs eval/refs_dfm/d*.py)"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.sandbox import execute
from eval.build_truth import derive

HERE = Path(__file__).parent
REFS = HERE / "refs_dfm"
TRUTH = HERE / "truth_dfm.json"


def build_ref(name: str, timeout_s: int = 120):
    code = (REFS / f"{name}.py").read_text()
    with tempfile.TemporaryDirectory() as td:
        res = execute(code, workdir=Path(td), timeout_s=timeout_s)
    if not res.ok:
        raise RuntimeError(f"reference {name} failed: {res.error}")
    return res.shape


def main() -> None:
    truth = {}
    for p in sorted(REFS.glob("*.py")):
        if p.stem.endswith("_naive"):
            continue
        truth[p.stem] = t = derive(build_ref(p.stem))
        print(p.stem, t["bbox"]["x"], t["bbox"]["y"], t["bbox"]["z"], t["hole_diameters"], t["volume_range"])
    TRUTH.write_text(json.dumps(truth, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {TRUTH} ({len(truth)} tasks)")


if __name__ == "__main__":
    main()
