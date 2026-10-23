"""Read-only bundled examples (examples/<name>/meta.json + v<n>/): listing and the detail payload served by
GET /api/examples and /api/runs/example-<name>. Stdlib only, so scripts/export_demo.py can reuse it without FastAPI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from web.server.store import file_list, file_sizes

EX_PREFIX = "example-"


def example_dirs(ex_dir: Path) -> dict[str, Path]:
    return {EX_PREFIX + d.name: d for d in sorted(ex_dir.glob("*")) if d.is_dir() and (d / "v1" / "run.json").exists()}


def example_files(d: Path, n: int) -> list[str]:
    v = d / f"v{n}"
    fl = file_list(v)
    if "part.glb" not in fl and (v / "part.step").exists():
        fl.append("part.glb")  # generated on first request by the server
    return fl


def example_detail(rid: str, d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    vs = sorted(int(p.name[1:]) for p in d.glob("v[0-9]*") if (p / "run.json").exists())
    runs = {str(n): json.loads((d / f"v{n}" / "run.json").read_text()) for n in vs}
    spec = (runs[str(vs[0])].get("spec") or {})
    return {"id": rid, "title": spec.get("part_type") or d.name, "request": meta.get("request", ""),
            "material": meta.get("material", spec.get("material", "")), "process": spec.get("process", ""),
            "config": meta.get("config", "C"), "created_at": meta.get("created_at") or datetime.fromtimestamp((d / "v1" / "run.json").stat().st_mtime, timezone.utc).isoformat(),
            "status": runs[str(vs[-1])].get("status", "success"), "versions": vs, "changes": meta.get("changes", {}), "synthetic": meta.get("synthetic", {}), "selection": meta.get("selection"), "source": meta.get("source"),
            "version_status": {str(n): runs[str(n)].get("status", "success") for n in vs},
            "runs": runs, "files": {str(n): example_files(d, n) for n in vs},
            "file_sizes": {str(n): file_sizes(d / f"v{n}", example_files(d, n)) for n in vs}, "example": True}
