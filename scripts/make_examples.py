"""Regenerate examples/ from genuine agent runs (real LLM calls; needs DEEPSEEK_API_KEY + cadquery, i.e. the docker image).

Each requirement runs N times (default 3) through the web server's job code path (web.server.jobs.Jobs), so outputs
are exactly what the app produces. One run per example is published unchanged to examples/<name>/; meta.json records
how it was chosen ("selection"). Summaries of all runs go to out/examples_runs/<name>/run<i>/ (gitignored).

usage (repo root, in the image):  python scripts/make_examples.py [--runs 3] [--only bracket,plate,u_bracket]
"""
import argparse
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from web.server.jobs import Jobs
from web.server.store import Store

# keep in sync with the prompt cards in web/ui/src/i18n.tsx
EXAMPLES = {
    "bracket": ("L 型铝支架:底板 100×60×6mm,立板沿长边,高 40mm、厚 3mm,底板四角各一个 M6 通孔,立板中间一个直径 20 的圆孔。",
                ["立板厚度改成 4mm"]),
    "plate": ("矩形安装板 120×80×8mm,四角各一个 M8 通孔,中心一个直径 30 的圆孔,四周倒角 R3。", []),
    "u_bracket": ("U 型支架:宽 50mm,长 80mm,高 35mm,壁厚 4mm,两侧壁各一个直径 8 的孔。", []),
}
MATERIAL, CONFIG = "6061", "C"
EVENTS_MAX = 100_000  # bytes; larger events.jsonl files are not published


def wait(store, jobs, rid, timeout=1800):
    end = time.time() + timeout
    while jobs.busy(rid) and time.time() < end:
        time.sleep(2)
    return (store.meta(rid) or {}).get("status")


def submit_run(store, jobs, req):
    rid = "r" + datetime.now().strftime("%H%M%S%f")
    store.vdir(rid, 1).mkdir(parents=True)
    store.update_meta(rid, id=rid, request=req, material=MATERIAL, process="", config=CONFIG, title=req[:40],
                      created_at=datetime.now(timezone.utc).isoformat(), status="queued", versions=[1], version_status={1: "queued"})
    jobs.submit(rid, 1, "run", request=req, material=MATERIAL, process="", config=CONFIG)
    return rid


def submit_modify(store, jobs, rid, change):
    m = store.meta(rid)
    base, n = store.latest_success(rid), max(m["versions"]) + 1
    store.vdir(rid, n).mkdir(parents=True)
    store.update_meta(rid, add_version=n, status="queued", version_status={n: "queued"}, change={n: change})
    jobs.submit(rid, n, "modify", base=base, change=change, config=CONFIG)


def summary(store, rid):
    m = store.meta(rid)
    vs = {}
    for n in m["versions"]:
        try:
            rj = json.loads((store.vdir(rid, n) / "run.json").read_text())
        except OSError:
            rj = {}
        vs[n] = {"status": m["version_status"].get(str(n)), "rounds": len(rj.get("rounds") or []),
                 "fix_rounds": max(len(rj.get("rounds") or []) - 1, 0),
                 "warnings": len(rj.get("final_issues") or []), "usage": rj.get("usage") or {}}
    return vs


def pick(sums):
    """Prefer: all versions succeeded > shows a real fix round > fewer final warnings > earlier run. Never edits outputs."""
    def key(i):
        s = sums[i]
        ok = all(v["status"] == "success" for v in s.values())
        fixes = sum(v["fix_rounds"] for v in s.values())
        return (not ok, fixes == 0, sum(v["warnings"] for v in s.values()), i)
    i = min(range(len(sums)), key=key)
    s = sums[i]
    ok = all(v["status"] == "success" for v in s.values())
    fixes = sum(v["fix_rounds"] for v in s.values())
    why = ("all versions succeeded" if ok else "no run fully succeeded; least bad") + \
          (f"; shows {fixes} real fix round(s)" if fixes else "; no run needed a fix round") + \
          f"; {sum(v['warnings'] for v in s.values())} final warning(s); earliest such run"
    why_zh = ("所有版本均通过" if ok else "没有一次完全通过,取最好的一次") + \
             (f";含 {fixes} 轮真实修正" if fixes else ";无需修正") + \
             f";终稿 {sum(v['warnings'] for v in s.values())} 条警告;同等条件下最早的一次"
    return i, why, why_zh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    names = [n for n in EXAMPLES if not a.only or n in a.only.split(",")]
    cfg = yaml.safe_load(open("config.yaml"))
    store = Store(Path(tempfile.mkdtemp(prefix="mkex_")))
    jobs = Jobs(store, cfg, max_workers=a.workers)
    ids = {n: [] for n in names}
    for name in names:
        for _ in range(a.runs):
            ids[name].append(submit_run(store, jobs, EXAMPLES[name][0]))
            time.sleep(0.01)
    for name in names:
        for rid in ids[name]:
            for change in EXAMPLES[name][1]:
                if wait(store, jobs, rid) != "success":
                    break
                submit_modify(store, jobs, rid, change)
    total = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    for name in names:
        sums = []
        for i, rid in enumerate(ids[name]):
            wait(store, jobs, rid)
            s = summary(store, rid)
            sums.append(s)
            dst = Path("out/examples_runs") / name / f"run{i}"
            shutil.rmtree(dst, ignore_errors=True)
            dst.mkdir(parents=True)
            shutil.copy(store.dir(rid) / "meta.json", dst / "meta.json")
            for n in s:
                for f in ("run.json", "log.txt"):
                    src = store.vdir(rid, n) / f
                    if src.exists():
                        (dst / f"v{n}").mkdir(exist_ok=True)
                        shutil.copy(src, dst / f"v{n}" / f)
                for k in total:
                    total[k] += s[n]["usage"].get(k, 0)
            print(name, f"run{i}", {n: (v["status"], v["rounds"]) for n, v in s.items()})
        i, why, why_zh = pick(sums)
        rid, m = ids[name][i], store.meta(ids[name][i])
        ex = Path("examples") / name
        shutil.rmtree(ex, ignore_errors=True)
        for n in m["versions"]:
            shutil.copytree(store.vdir(rid, n), ex / f"v{n}")
            ev = ex / f"v{n}" / "events.jsonl"
            if ev.exists() and ev.stat().st_size > EVENTS_MAX:
                ev.unlink()
        (ex / "meta.json").write_text(json.dumps({
            "request": m["request"], "material": MATERIAL, "config": CONFIG, "created_at": m["created_at"],
            "changes": m.get("changes", {}), "source": "scripts/make_examples.py (genuine agent run, outputs unedited)",
            "selection": {"runs": len(sums), "picked": i, "reason": why, "reason_zh": why_zh,
                          "summary": [{n: (v["status"], v["rounds"]) for n, v in s.items()} for s in sums]},
        }, ensure_ascii=False, indent=1))
        print(name, "picked", i, why)
    print("total usage", total)
    jobs.pool.shutdown(wait=True)


if __name__ == "__main__":
    main()
