#!/usr/bin/env python3
"""Export the bundled examples as static files for the read-only web demo (web/ui built with VITE_DEMO=1).

  <out>/examples.json                 same payload as GET /api/examples
  <out>/runs/<id>/v<n>/<file>         every file listed for that version (as served by /api/runs/<id>/v<n>/<file>)

Needs only the standard library (no FastAPI, no cadquery), so the Pages workflow can run it directly.
usage (repo root):  python3 scripts/export_demo.py --out web/ui/dist-demo/demo-data
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web.server.examples import example_detail, example_dirs  # noqa: E402


def export(examples_dir: Path, out: Path) -> list[dict]:
    details = [example_detail(rid, d) for rid, d in example_dirs(examples_dir).items()]
    for det in details:
        d = examples_dir / det["id"].removeprefix("example-")
        for n, files in det["files"].items():
            for f in files:
                src = d / f"v{n}" / f
                if not src.is_file():  # part.glb is generated lazily by the server; bundled examples ship it
                    raise SystemExit(f"missing {src}")
                dst = out / "runs" / det["id"] / f"v{n}" / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
    out.mkdir(parents=True, exist_ok=True)
    (out / "examples.json").write_text(json.dumps(details, ensure_ascii=False))
    return details


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", default=str(ROOT / "examples"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    details = export(Path(a.examples), out)
    print(f"exported {len(details)} examples to {out}")


if __name__ == "__main__":
    main()
