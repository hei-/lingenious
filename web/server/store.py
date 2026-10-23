"""File-backed run store: data/runs/<id>/{meta.json,v<n>/...}; per-version events.jsonl for SSE replay."""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
FILES = ("part.py", "part.step", "part.glb", "render.png", "thumb.png", "drawing.pdf", "drawing.dxf", "drawing.png", "run.json", "log.txt")
ROUND_RE = re.compile(r"^rounds/r\d{1,3}\.glb$")
TERMINAL = ("done", "error")
_lock = threading.RLock()


def _atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


class Store:
    def __init__(self, root: Path):
        self.runs = Path(root) / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    def dir(self, run_id: str) -> Path:
        if not ID_RE.match(run_id):
            raise KeyError(run_id)
        return self.runs / run_id

    def vdir(self, run_id: str, n: int) -> Path:
        return self.dir(run_id) / f"v{int(n)}"

    def meta(self, run_id: str) -> Optional[dict]:
        try:
            return json.loads((self.dir(run_id) / "meta.json").read_text())
        except (KeyError, OSError, ValueError):
            return None

    def update_meta(self, run_id: str, **kw) -> dict:
        with _lock:
            m = self.meta(run_id) or {}
            vs = kw.pop("version_status", None)
            if vs:
                m.setdefault("version_status", {}).update({str(k): v for k, v in vs.items()})
            ch = kw.pop("change", None)
            if ch:
                m.setdefault("changes", {}).update({str(k): v for k, v in ch.items()})
            nv = kw.pop("add_version", None)
            if nv and nv not in m.setdefault("versions", []):
                m["versions"].append(nv)
            m.update(kw)
            d = self.dir(run_id)
            d.mkdir(parents=True, exist_ok=True)
            _atomic(d / "meta.json", json.dumps(m, ensure_ascii=False, indent=2))
            return m

    def list(self) -> list[dict]:
        out = []
        for d in self.runs.iterdir():
            m = self.meta(d.name) if d.is_dir() else None
            if m:
                out.append({k: m.get(k) for k in ("id", "title", "status", "created_at", "versions")})
        return sorted(out, key=lambda m: m["created_at"] or "", reverse=True)

    def latest_success(self, run_id: str) -> Optional[int]:
        m = self.meta(run_id) or {}
        vs = m.get("version_status", {})
        for n in sorted(m.get("versions", []), reverse=True):
            if vs.get(str(n)) == "success" and (self.vdir(run_id, n) / "part.py").exists():
                return n
        return None

    # --- events
    def append_event(self, run_id: str, n: int, name: str, data: dict) -> None:
        with _lock, open(self.vdir(run_id, n) / "events.jsonl", "a") as f:
            f.write(json.dumps({"event": name, "data": data}, ensure_ascii=False) + "\n")

    def events_from(self, run_id: str, n: int, offset: int) -> list[dict]:
        try:
            lines = (self.vdir(run_id, n) / "events.jsonl").read_text().splitlines()
        except OSError:
            return []
        out = []
        for ln in lines[offset:]:
            try:
                out.append(json.loads(ln))
            except ValueError:
                break
        return out


# user-facing files bundled in bundle.zip (no glb meshes, no events/meta)
BUNDLE = ("part.step", "part.py", "drawing.pdf", "drawing.dxf", "drawing.png", "render.png", "run.json", "log.txt")
_SUFFIX = {"part.step": ".step", "part.py": ".py", "part.glb": ".glb", "drawing.pdf": ".pdf", "drawing.dxf": ".dxf",
           "drawing.png": "_drawing.png", "render.png": "_render.png", "thumb.png": "_thumb.png", "run.json": "_run.json", "log.txt": "_log.txt", "bundle.zip": ".zip"}
_UNSAFE = re.compile(r"[^\w\u4e00-\u9fff\u3400-\u4dbf.\-]+")


def safe_title(title: str) -> str:
    """Filesystem-safe title: keep letters/digits/CJK/._-, collapse the rest to '_', max 60 chars."""
    t = _UNSAFE.sub("_", (title or "").strip()).strip("._-")
    return t[:60].rstrip("._-") or "part"


def download_name(title: str, n: int, file: str) -> str:
    """<title>_v<n>.<ext> (see docs/web-app.md); rounds/r<k>.glb -> <title>_v<n>_r<k>.glb."""
    base = f"{safe_title(title)}_v{int(n)}"
    if file.startswith("rounds/"):
        return f"{base}_{file[7:-4]}.glb"
    return base + _SUFFIX.get(file, "_" + file)


def file_sizes(vdir: Path, names: list[str]) -> dict[str, int]:
    out = {}
    for f in names:
        try:
            out[f] = (vdir / f).stat().st_size
        except OSError:
            pass
    return out


def file_list(vdir: Path) -> list[str]:
    rg = sorted((f"rounds/{p.name}" for p in (vdir / "rounds").glob("r*.glb") if ROUND_RE.match(f"rounds/{p.name}")),
                key=lambda s: int(s[8:-4])) if (vdir / "rounds").is_dir() else []
    return [f for f in FILES if (vdir / f).is_file()] + rg
