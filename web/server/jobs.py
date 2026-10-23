"""Background job runner: executes core.agent.run/modify, persists events, produces artifacts."""
from __future__ import annotations

import json
import os
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core import agent
from core.llm import LLM
from core.models import Issue, PartSpec
from web.server.store import Store

_plot_lock = threading.Lock()  # matplotlib/pyplot is not thread-safe


def make_llm(cfg: dict) -> LLM:  # indirection so tests can swap in a fake
    return LLM(cfg)


def llm_configured(cfg: dict) -> bool:
    return bool(os.environ.get(cfg["llm"].get("api_key_env", "DEEPSEEK_API_KEY")))


def _scrub(msg: str, cfg: dict) -> str:
    key = os.environ.get(cfg["llm"].get("api_key_env", "DEEPSEEK_API_KEY"), "")
    return msg.replace(key, "***") if key else msg


def load_prev(vdir: Path) -> agent.RunResult:
    """Rebuild the previous RunResult from part.py + run.json (see core/modify_cli.py)."""
    rj = json.loads((vdir / "run.json").read_text())
    rounds = [agent.Round(r.get("n", i + 1), r.get("code", ""), [Issue(**x) for x in r.get("issues", [])], r.get("seconds", 0.0))
              for i, r in enumerate(rj.get("rounds") or [])]
    return agent.RunResult(status="success", spec=PartSpec(**rj["spec"]), code=(vdir / "part.py").read_text(), rounds=rounds)


class Jobs:
    def __init__(self, store: Store, cfg: dict, max_workers: int = 2, max_queued: int = 20):
        self.store, self.cfg, self.max_queued = store, cfg, max_queued
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")
        self.active: set[str] = set()
        self.pending = 0
        self._lock = threading.Lock()

    def busy(self, run_id: str) -> bool:
        return run_id in self.active

    def full(self) -> bool:
        return self.pending >= self.max_queued

    def submit(self, run_id: str, n: int, kind: str, **kw) -> None:
        with self._lock:
            self.active.add(run_id)
            self.pending += 1
        self.pool.submit(self._work, run_id, n, kind, kw)

    def _work(self, run_id: str, n: int, kind: str, kw: dict) -> None:
        st, vdir = self.store, self.store.vdir(run_id, n)

        glbs = {}

        def emit(name, data):
            if name == "round" and data.get("exec_ok"):  # per-round geometry, from that round's STEP
                rg = self._round_glb(vdir, data["n"])
                if rg:
                    glbs[data["n"]] = data["glb"] = rg
            st.append_event(run_id, n, name, data)
            if name == "round" and data.get("glb"):
                st.append_event(run_id, n, "artifact", {"name": data["glb"]})

        status = "error"
        try:
            st.update_meta(run_id, status="running", version_status={n: "running"})
            llm = make_llm(self.cfg)
            if kind == "run":
                res = agent.run(llm, kw["request"], self.cfg, vdir, kw["config"], kw["material"], kw["process"], on_event=emit)
            else:
                res = agent.modify(llm, load_prev(self.store.vdir(run_id, kw["base"])), kw["change"], self.cfg, vdir, kw["config"], on_event=emit)
            agent.save(res, vdir)
            for f in ("part.py", "part.step", "run.json", "log.txt"):
                if (vdir / f).exists():
                    emit("artifact", {"name": f})
            if glbs:
                rj = json.loads((vdir / "run.json").read_text())
                for r in rj["rounds"]:
                    if r["n"] in glbs:
                        r["glb"] = glbs[r["n"]]
                (vdir / "run.json").write_text(json.dumps(rj, ensure_ascii=False, indent=2))
            for d in vdir.glob("round[0-9]*"):
                shutil.rmtree(d, ignore_errors=True)
            if res.exec and res.exec.ok:
                self._artifacts(res, vdir, emit)
            status = res.status
            if kind == "run" and res.spec:
                st.update_meta(run_id, title=(res.spec.part_type or kw["request"])[:60])
            emit("done", {"status": status, "version": n, "usage": res.usage})
        except Exception as e:
            traceback.print_exc()
            emit("error", {"message": _scrub(f"{type(e).__name__}: {e}", self.cfg)[:500]})
        finally:
            st.update_meta(run_id, status=status, version_status={n: status})
            with self._lock:
                self.active.discard(run_id)
                self.pending -= 1

    def _artifacts(self, res, vdir: Path, emit) -> None:
        from core.render import render, render_thumb
        from web.server.meshing import step_to_glb
        title = f"{vdir.name} {res.spec.part_type}"
        steps = [
            ("render.png", lambda: _locked(render, res.exec.shape, vdir / "render.png", title=title)),
            ("thumb.png", lambda: _locked(render_thumb, res.exec.shape, vdir / "thumb.png")),
            ("part.glb", lambda: step_to_glb(res.exec.step_path if res.exec.step_path and Path(res.exec.step_path).exists() else vdir / "part.step", vdir / "part.glb")),
            ("drawing", lambda: _locked(_draw, res, vdir)),
        ]
        for name, fn in steps:
            try:
                fn()
            except Exception as e:  # artifacts are best-effort; the run itself succeeded
                emit("artifact_failed", {"name": name, "message": str(e)[:200]})
                continue
            if name == "drawing":
                for f in ("drawing.pdf", "drawing.dxf", "drawing.png"):
                    emit("artifact", {"name": f})
            else:
                emit("artifact", {"name": name})

    @staticmethod
    def _round_glb(vdir: Path, k: int):
        step = vdir / f"round{k}" / "part.step"
        if not step.exists():
            return None
        try:
            from web.server.meshing import step_to_glb
            step_to_glb(step, vdir / "rounds" / f"r{k}.glb")
            return f"rounds/r{k}.glb"
        except Exception:
            return None

    def recover(self) -> None:
        """Runs left queued/running by a previous process cannot continue."""
        for m in self.store.list():
            full = self.store.meta(m["id"]) or {}
            for n, s in (full.get("version_status") or {}).items():
                if s in ("queued", "running"):
                    if (self.store.vdir(m["id"], int(n))).exists():
                        self.store.append_event(m["id"], int(n), "error", {"message": "server restarted before the run finished"})
                    self.store.update_meta(m["id"], status="error", version_status={n: "error"})


def _locked(fn, *a, **k):
    with _plot_lock:
        return fn(*a, **k)


def _draw(res, vdir: Path):
    from core.drawing import draw
    draw(res.exec.shape, vdir, name=res.spec.part_type, material=res.spec.material)
