"""Poll the Bitable for work and run the CAD agent in Docker (trigger rules: README.md).

usage: python3 adapters/feishu_bitable/poll.py [--once] [--interval 10]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.feishu_bitable import larkio, logic  # noqa: E402

STATE = ROOT / "out" / "bitable" / "state.json"
OUT = ROOT / "out" / "bitable"
IMAGE = os.environ.get("LINGENIOUS_IMAGE", "lingenious:dev")


# ---------- I/O helpers ----------
def docker(*args: str, check: bool = False, timeout: int = 1500) -> subprocess.CompletedProcess:
    p = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("docker %s: %s" % (args[0], (p.stderr or p.stdout)[-400:]))
    return p


class Table:
    def __init__(self, st: Dict[str, str]):
        self.base, self.tid = st["base_token"], st["table_id"]

    def list(self) -> List[Dict[str, Any]]:
        d = larkio.run(["base", "+record-list", "--base-token", self.base, "--table-id", self.tid, "--json", "--limit", "200"])
        return logic.parse_records(d["data"])

    def update(self, rid: str, fields: Dict[str, Any]) -> None:
        larkio.run(["base", "+record-batch-update", "--base-token", self.base, "--table-id", self.tid,
                    "--json", json.dumps({"update_records": {rid: fields}}, ensure_ascii=False)])

    def upload(self, rid: str, field: str, cwd: Path, files: List[str]) -> None:
        args = ["base", "+record-upload-attachment", "--base-token", self.base, "--table-id", self.tid,
                "--record-id", rid, "--field-id", field]
        for f in files:
            args += ["--file", "./" + f]
        larkio.run(args, cwd=str(cwd))


def run_container(rid: str, cmd: List[str], copy_in: Dict[Path, str], copy_out_from: str, copy_out_to: Path) -> str:
    """create -> cp in -> start -a -> cp out -> always rm."""
    cid = "cad-bt-%s-%d" % (rid[-8:].lower(), os.getpid())
    try:
        docker("create", "--name", cid, "--env-file", str(ROOT / ".env"), IMAGE, *cmd, check=True)
        for src, dst in copy_in.items():
            docker("cp", str(src), "%s:%s" % (cid, dst), check=True)
        p = docker("start", "-a", cid)
        print("  container exit=%s" % p.returncode, flush=True)
        stdout = p.stdout
        if copy_out_to.exists():
            shutil.rmtree(str(copy_out_to))
        copy_out_to.parent.mkdir(parents=True, exist_ok=True)
        docker("cp", "%s:%s" % (cid, copy_out_from), str(copy_out_to))
        return stdout
    finally:
        docker("rm", "-f", cid)


def stage_upload(vdir: Path, version: int) -> Dict[str, List[str]]:
    plan = logic.attachment_plan({f: (vdir / f).exists() for f in
                                  ["render.png", "part.step", "part.py", "drawing.pdf", "drawing.dxf"]}, version)
    up = vdir.parent / ("upload_v%d" % version)
    if up.exists():
        shutil.rmtree(str(up))
    up.mkdir(parents=True)
    staged: Dict[str, List[str]] = {}
    for field, files in plan.items():
        names = []
        for f in files:
            n = "v%d_%s" % (version, f)
            shutil.copy(str(vdir / f), str(up / n))
            names.append(n)
        staged[field] = names
    return staged


def finish(tbl: Table, rec: Dict[str, Any], vdir: Path, version: int, rounds: int, change: str = "") -> None:
    run = json.loads((vdir / "run.json").read_text())
    log_text = (vdir / "log.txt").read_text() if (vdir / "log.txt").exists() else ""
    fields = logic.build_update_fields(run, log_text, rounds, version, prev_log=rec["log"], change=change)
    if run.get("status") == "success" or not change:  # failed first runs still attach what exists
        staged = stage_upload(vdir, version)
        for field, names in staged.items():
            tbl.upload(rec["record_id"], field, vdir.parent / ("upload_v%d" % version), names)
    else:  # modify did not succeed: keep the previously passed version
        fields = logic.error_fields("v%d 修改未通过(%s)\n%s" % (version, change, log_text), prev_log=rec["log"],
                                    restore_status="已通过")
        fields["修改要求"] = None
    tbl.update(rec["record_id"], fields)


def process_new(tbl: Table, rec: Dict[str, Any]) -> None:
    rid = rec["record_id"]
    rdir = OUT / rid
    cmd = ["python", "-W", "ignore", "-m", "core.cli", rec["desc"], "--out", "/tmp/out/" + rid]
    if rec["material"]:
        cmd += ["--material", rec["material"]]
    stdout = run_container(rid, cmd, {}, "/tmp/out/%s" % rid, rdir)
    vdir = rdir / "v1"
    if not (vdir / "run.json").exists():
        miss = logic.parse_need_info(stdout)
        if miss is None:
            raise RuntimeError("容器未产出 run.json: " + stdout[-500:])
        run = {"status": "need_info", "spec": {"missing": miss}}
        tbl.update(rid, logic.build_update_fields(run, "需补充信息,未进入生成", 0, 1))
        return
    run = json.loads((vdir / "run.json").read_text())
    finish(tbl, rec, vdir, 1, len(run.get("rounds") or []))


def process_modify(tbl: Table, rec: Dict[str, Any]) -> None:
    rid = rec["record_id"]
    rdir = OUT / rid
    prev_v = rec["version"] or 1
    prev = rdir / ("v%d" % prev_v)
    if not (prev / "part.py").exists() or not (prev / "run.json").exists():
        raise RuntimeError("找不到上一版本文件: %s" % prev)
    new_v = prev_v + 1
    prev_rounds = rec["rounds"]
    cmd = ["python", "-W", "ignore", "-m", "core.modify_cli", "--script", "/tmp/in_part.py", "--run-json", "/tmp/in_run.json",
           "--change", rec["change"], "--out", "/tmp/out/v%d" % new_v, "--version", str(new_v)]
    stdout = run_container(rid, cmd, {prev / "part.py": "/tmp/in_part.py", prev / "run.json": "/tmp/in_run.json"},
                  "/tmp/out/v%d" % new_v, rdir / ("v%d" % new_v))
    vdir = rdir / ("v%d" % new_v)
    if not (vdir / "run.json").exists():
        raise RuntimeError("容器未产出 run.json: " + stdout[-500:])
    run = json.loads((vdir / "run.json").read_text())
    finish(tbl, rec, vdir, new_v, prev_rounds + len(run.get("rounds") or []), change=rec["change"])


def handle(tbl: Table, kind: str, rec: Dict[str, Any]) -> None:
    rid = rec["record_id"]
    print("[%s] %s" % (kind, rid), flush=True)
    tbl.update(rid, {"状态": ["生成中"]})
    try:
        (process_new if kind == "new" else process_modify)(tbl, rec)
        print("  done", flush=True)
    except Exception as e:  # never leave a row in 生成中
        traceback.print_exc()
        try:
            tbl.update(rid, logic.error_fields("%s: %s" % (type(e).__name__, e), prev_log=rec["log"]))
        except Exception:
            traceback.print_exc()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    a = ap.parse_args()
    st = json.loads(STATE.read_text())
    tbl = Table(st)
    while True:
        try:
            for kind, rec in logic.pending_work(tbl.list()):
                handle(tbl, kind, rec)
        except Exception:
            traceback.print_exc()
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
