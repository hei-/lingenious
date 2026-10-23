"""Lingenious web backend. Run: uvicorn web.server.app:app   (contract: docs/web-app.md)"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import tempfile
import uuid
import zipfile
from urllib.parse import quote
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.config import load_config
from web.server import examples, jobs as jobs_mod
from web.server.auth import COOKIE, OPEN_PATHS, Auth
from web.server.store import BUNDLE, FILES, ID_RE, ROUND_RE, TERMINAL, Store, download_name, file_list, file_sizes
from web.server.examples import EX_PREFIX

ROOT = Path(__file__).resolve().parents[2]
mimetypes.add_type("model/gltf-binary", ".glb")
MEDIA = {".step": "application/octet-stream", ".dxf": "application/dxf", ".py": "text/plain; charset=utf-8",
         ".txt": "text/plain; charset=utf-8", ".json": "application/json"}


def _disposition(name: str) -> str:
    """attachment with an ASCII fallback plus RFC 5987 filename* (keeps CJK)."""
    ascii_name = name
    if not name.isascii():  # e.g. 支架_v2.step -> part_v2.step for clients without filename* support
        i = name.rfind("_v")
        ascii_name = "part" + name[i:] if i >= 0 else "download"
    ascii_name = ascii_name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"


class RunReq(BaseModel):
    request: str = Field(min_length=1, max_length=2000)
    material: str = Field("", max_length=100)
    process: str = Field("", max_length=100)
    config: str = Field("C", pattern="^[ABC]$")


class LoginReq(BaseModel):
    token: str = Field(max_length=1000)


class ModifyReq(BaseModel):
    change: str = Field(min_length=1, max_length=1000)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def create_app(data_dir: Optional[Path] = None, cfg: Optional[dict] = None, examples_dir: Optional[Path] = None,
               access_token: Optional[str] = None) -> FastAPI:
    cfg = cfg or load_config(os.environ.get("LINGENIOUS_CONFIG", ROOT / "config.yaml"))
    data = Path(data_dir or os.environ.get("LINGENIOUS_DATA", ROOT / "data"))
    ex_dir = Path(examples_dir or ROOT / "examples")
    auth = Auth(access_token if access_token is not None else os.environ.get("LINGENIOUS_ACCESS_TOKEN"))
    store = Store(data)
    jobs = jobs_mod.Jobs(store, cfg, _int_env("LINGENIOUS_MAX_WORKERS", cfg.get("web", {}).get("max_workers", 2)))
    cache = data / "cache" / "examples"

    @asynccontextmanager
    async def lifespan(app):
        jobs.recover()
        yield
        jobs.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Lingenious", lifespan=lifespan)
    app.state.store, app.state.jobs = store, jobs

    @app.middleware("http")
    async def require_auth(request: Request, call_next):
        p = request.url.path
        if auth.required and (p == "/api" or p.startswith("/api/")) and p not in OPEN_PATHS and not auth.authenticated(request):
            return JSONResponse({"detail": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)

    def need_key():
        if not jobs_mod.llm_configured(cfg):
            raise HTTPException(503, "LLM API key is not configured on the server")

    def run_or_404(run_id: str) -> dict:
        m = store.meta(run_id) if ID_RE.match(run_id) else None
        if not m:
            raise HTTPException(404, "run not found")
        return m

    # ---- examples (read-only)
    def example_dirs() -> dict[str, Path]:
        return examples.example_dirs(ex_dir)

    def example_vdir(d: Path, n: int, make_glb: bool = False) -> Path:
        v = d / f"v{n}"
        if make_glb and not (v / "part.glb").exists() and (v / "part.step").exists():
            c = cache / d.name / f"v{n}"
            if not (c / "part.glb").exists():
                from web.server.meshing import step_to_glb
                step_to_glb(v / "part.step", c / "part.glb")
        return v

    example_detail = examples.example_detail

    # ---- API
    @app.get("/api/health")
    def health(request: Request):
        return {"ok": True, "llm_configured": jobs_mod.llm_configured(cfg), "auth_required": auth.required,
                "authenticated": auth.authenticated(request)}

    @app.post("/api/auth/login")
    def login(req: LoginReq, request: Request):
        if not auth.required:
            return {"ok": True, "auth_required": False}
        ip = auth.client(request)
        wait = auth.retry_after(ip)
        if wait:
            return JSONResponse({"detail": "too many failed attempts, try again later"}, status_code=429, headers={"Retry-After": str(wait)})
        if not auth.check_token(req.token):
            auth.record_failure(ip)
            raise HTTPException(401, "invalid token")
        auth.record_success(ip)
        resp = JSONResponse({"ok": True, "auth_required": True})
        resp.set_cookie(COOKIE, auth.session_value(), httponly=True, samesite="strict", path="/", max_age=30 * 86400,
                        secure=request.url.scheme == "https")
        return resp

    @app.post("/api/auth/logout")
    def logout():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return resp

    @app.post("/api/runs")
    def create_run(req: RunReq):
        need_key()
        if jobs.full():
            raise HTTPException(429, "too many queued runs, try again later")
        rid = uuid.uuid4().hex[:12]
        store.vdir(rid, 1).mkdir(parents=True)
        store.update_meta(rid, id=rid, request=req.request, material=req.material, process=req.process, config=req.config,
                          title=req.request[:40], created_at=datetime.now(timezone.utc).isoformat(), status="queued",
                          versions=[1], version_status={1: "queued"})
        jobs.submit(rid, 1, "run", request=req.request, material=req.material, process=req.process, config=req.config)
        return {"id": rid}

    @app.post("/api/runs/{run_id}/modify")
    def modify_run(run_id: str, req: ModifyReq):
        if run_id.startswith(EX_PREFIX):
            raise HTTPException(403, "examples are read-only")
        m = run_or_404(run_id)
        need_key()
        if jobs.busy(run_id):
            raise HTTPException(409, "a version of this run is still running")
        if jobs.full():
            raise HTTPException(429, "too many queued runs, try again later")
        base = store.latest_success(run_id)
        if base is None:
            raise HTTPException(409, "no successful version to modify")
        n = max(m["versions"]) + 1
        store.vdir(run_id, n).mkdir(parents=True)
        store.update_meta(run_id, add_version=n, status="queued", version_status={n: "queued"}, change={n: req.change})
        jobs.submit(run_id, n, "modify", base=base, change=req.change, config=m.get("config", "C"))
        return {"id": run_id, "version": n}

    @app.get("/api/runs")
    def list_runs():
        return store.list()

    @app.get("/api/examples")
    def list_examples():
        return [example_detail(rid, d) for rid, d in example_dirs().items()]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        if run_id.startswith(EX_PREFIX):
            d = example_dirs().get(run_id)
            if not d:
                raise HTTPException(404, "run not found")
            return example_detail(run_id, d)
        m = run_or_404(run_id)
        runs, files, sizes = {}, {}, {}
        for n in m["versions"]:
            v = store.vdir(run_id, n)
            files[str(n)] = file_list(v)
            sizes[str(n)] = file_sizes(v, files[str(n)])
            try:
                runs[str(n)] = json.loads((v / "run.json").read_text())
            except (OSError, ValueError):
                runs[str(n)] = None
        return {**m, "runs": runs, "files": files, "file_sizes": sizes}

    def version_dir(run_id: str, n: int) -> tuple[Path, str]:
        """(version dir, title) for a run or example; 404 when either is unknown."""
        if run_id.startswith(EX_PREFIX):
            d = example_dirs().get(run_id)
            if not d:
                raise HTTPException(404, "run not found")
            v = d / f"v{n}"
            if not (v / "run.json").is_file():
                raise HTTPException(404, "version not found")
            return v, example_detail(run_id, d)["title"]
        m = run_or_404(run_id)
        if n not in m.get("versions", []):
            raise HTTPException(404, "version not found")
        return store.vdir(run_id, n), m.get("title") or run_id

    @app.get("/api/runs/{run_id}/v{n}/bundle.zip")
    def bundle(run_id: str, n: int):
        v, title = version_dir(run_id, n)
        names = [f for f in BUNDLE if (v / f).is_file()]
        if not names:
            raise HTTPException(404, "no files yet")
        buf = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in names:
                z.write(v / f, download_name(title, n, f))
        buf.seek(0)

        def chunks():
            try:
                while block := buf.read(64 * 1024):
                    yield block
            finally:
                buf.close()

        return StreamingResponse(chunks(), media_type="application/zip",
                                 headers={"Content-Disposition": _disposition(download_name(title, n, "bundle.zip"))})

    @app.get("/api/runs/{run_id}/v{n}/{file:path}")
    def get_file(run_id: str, n: int, file: str, download: bool = Query(False)):
        if file not in FILES and not ROUND_RE.match(file):
            raise HTTPException(404, "file not found")
        if run_id.startswith(EX_PREFIX):
            d = example_dirs().get(run_id)
            if not d:
                raise HTTPException(404, "run not found")
            v = example_vdir(d, n, make_glb=file == "part.glb")
            p = v / file
            if file == "part.glb" and not p.exists():
                p = cache / d.name / f"v{n}" / file
        else:
            run_or_404(run_id)
            p = store.vdir(run_id, n) / file
        if not p.is_file():
            raise HTTPException(404, "file not found")
        headers = {}
        if download:
            title = example_detail(run_id, example_dirs()[run_id])["title"] if run_id.startswith(EX_PREFIX) else (store.meta(run_id) or {}).get("title") or run_id
            headers["Content-Disposition"] = _disposition(download_name(title, n, file))
        return FileResponse(p, headers=headers, media_type=MEDIA.get(p.suffix) or mimetypes.guess_type(p.name)[0] or "application/octet-stream")

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, version: Optional[int] = Query(None, ge=1)):
        if run_id.startswith(EX_PREFIX):
            d = example_dirs().get(run_id)
            if not d:
                raise HTTPException(404, "run not found")
            vs = example_detail(run_id, d)["versions"]
            v = version or vs[-1]
            if v not in vs:
                raise HTTPException(404, "version not found")
            evs = [{"event": "done", "data": {"status": "success", "version": v, "usage": {}}}]
            return StreamingResponse(iter([_sse(e) for e in evs]), media_type="text/event-stream")
        m = run_or_404(run_id)
        v = version or max(m["versions"])
        if v not in m["versions"]:
            raise HTTPException(404, "version not found")

        async def gen():
            off, idle = 0, 0.0
            while True:
                evs = store.events_from(run_id, v, off)
                for e in evs:
                    off += 1
                    yield _sse(e)
                    if e["event"] in TERMINAL:
                        return
                if evs:
                    idle = 0.0
                    continue
                if not jobs.busy(run_id) and (store.meta(run_id) or {}).get("version_status", {}).get(str(v)) not in ("queued", "running"):
                    if not store.events_from(run_id, v, off):
                        yield _sse({"event": "error", "data": {"message": "run ended without a result"}})
                        return
                    continue
                await asyncio.sleep(0.15)
                idle += 0.15
                if idle >= 15:
                    idle = 0.0
                    yield ": ping\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- static UI with SPA fallback
    dist = Path(os.environ.get("LINGENIOUS_UI_DIST", ROOT / "web" / "ui" / "dist"))
    if dist.is_dir():
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            p = (dist / path).resolve()
            if path and p.is_file() and dist.resolve() in p.parents:
                return FileResponse(p)
            return FileResponse(dist / "index.html")

    return app


def _sse(e: dict) -> str:
    return f"event: {e['event']}\ndata: {json.dumps(e['data'], ensure_ascii=False)}\n\n"


app = create_app()
