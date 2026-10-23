"""Derive ground truth from the verified reference solids: python -m eval.build_truth -> eval/truth.json"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.checks.features import find_holes
from core.sandbox import execute

HERE = Path(__file__).parent
REFS = HERE / "refs"
TRUTH = HERE / "truth.json"


def derive(shape) -> dict:
    bb = shape.BoundingBox()
    holes = sorted(round(h.diameter, 2) for h in find_holes(shape))
    v = shape.Volume()
    return {
        "bbox": {"x": round(bb.xlen, 2), "y": round(bb.ylen, 2), "z": round(bb.zlen, 2), "tol": 0.5},
        "hole_count": len(holes),
        "hole_diameters": holes,
        "diameter_tol": 0.15,
        "volume_range": [round(0.97 * v), round(1.03 * v)],
    }


def build_ref(task_id: str, timeout_s: int = 120):
    code = (REFS / f"{task_id}.py").read_text()
    with tempfile.TemporaryDirectory() as td:
        res = execute(code, workdir=Path(td), timeout_s=timeout_s)
    if not res.ok:
        raise RuntimeError(f"reference {task_id} failed: {res.error}")
    return res.shape


def main() -> None:
    truth = {}
    for p in sorted(REFS.glob("*.py")):
        truth[p.stem] = derive(build_ref(p.stem))
        t = truth[p.stem]
        print(p.stem, t["bbox"]["x"], t["bbox"]["y"], t["bbox"]["z"], t["hole_diameters"], t["volume_range"])
    TRUTH.write_text(json.dumps(truth, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {TRUTH} ({len(truth)} tasks)")


if __name__ == "__main__":
    main()
