"""python -m eval.runner --configs A B C --repeat 3 --workers 4 [--ids e1 m1] -> eval/results/results.csv

Grading is against ground-truth assertions (eval/tasks.py), independent of the LLM-parsed spec.
Starts over by default (an existing results.csv in --out is replaced). With --resume, rows already in results.csv
(task, config, rep) are kept and skipped, e.g. after an interrupted run.
"""
from __future__ import annotations

import argparse
import csv
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


from core import agent
from core.config import load_config
from core.checks import run_checks
from core.llm import LLM
from core.models import Assertions, PartSpec
from core.sandbox import execute
from eval.tasks import TASKS as MAIN_TASKS

FIELDS = ["task", "level", "config", "rep", "model", "status", "first_pass", "final_pass", "rounds",
          "exec_ok", "l3_errors", "disputes", "failed_rules", "prompt_tokens", "completion_tokens", "seconds"]
_lock = threading.Lock()


def grade(code: str, truth: dict, cfg: dict, workdir: Path):
    """Ground-truth grading: (exec_ok, passes L1+L2 vs truth, L3 error count, failing L1/L2 rule ids)."""
    res = execute(code, workdir=workdir, timeout_s=cfg["sandbox"]["timeout_s"])
    if not res.ok:
        return False, False, 0, ["exec_error"]
    spec = PartSpec(assertions=Assertions.model_validate(truth))
    l12 = [i.rule for i in run_checks(res.shape, spec, cfg, levels=("L1", "L2")) if i.severity == "error"]
    l3 = [i for i in run_checks(res.shape, PartSpec(), cfg, levels=("L3",)) if i.severity == "error"]
    return True, not l12, len(l3), l12


def one(t: dict, config: str, rep: int, cfg: dict, out: Path) -> dict:
    llm = LLM(cfg)
    wd = out / "runs" / f"{t['id']}_{config}_{rep}"
    t0 = time.time()
    row = {"task": t["id"], "level": t["level"], "config": config, "rep": rep, "model": cfg["llm"]["model"],
           "status": "error", "first_pass": False, "final_pass": False, "rounds": 0, "exec_ok": False,
           "l3_errors": 0, "disputes": 0, "failed_rules": "", "prompt_tokens": 0, "completion_tokens": 0, "seconds": 0}
    try:
        r = agent.run(llm, t["text"], cfg, wd, config, material="6061")
        row.update(status=r.status, rounds=len(r.rounds),
                   prompt_tokens=r.usage.get("prompt_tokens"), completion_tokens=r.usage.get("completion_tokens"))
        row["disputes"] = sum(1 for rd in r.rounds if "ASSERTION_DISPUTE" in rd.code)
        if r.rounds:
            row["first_pass"] = grade(r.rounds[0].code, t["truth"], cfg, wd / "g_first")[1]
            ok, passed, l3, rules = grade(r.code, t["truth"], cfg, wd / "g_final")
            row.update(exec_ok=ok, final_pass=passed, l3_errors=l3, failed_rules=";".join(rules))
    except Exception as e:  # keep the sweep going; recorded as status=error
        row["failed_rules"] = f"{type(e).__name__}: {str(e)[:80]}"
    row["seconds"] = round(time.time() - t0, 1)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--taskset", choices=["main", "dfm"], default="main")
    ap.add_argument("--out", default=None, help="default: eval/results (main) or eval/results_dfm (dfm)")
    ap.add_argument("--resume", action="store_true", help="keep rows already in results.csv and skip them")
    a = ap.parse_args()
    if a.taskset == "dfm":
        from eval.tasks_dfm import TASKS
    else:
        TASKS = MAIN_TASKS
    a.out = a.out or ("eval/results_dfm" if a.taskset == "dfm" else "eval/results")

    cfg = load_config("config.yaml")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "results.csv"
    done = set()
    if csv_path.exists() and not a.resume:
        csv_path.unlink()  # fresh run: the committed results would otherwise make every run a no-op
    if csv_path.exists():
        done = {(r["task"], r["config"], int(r["rep"])) for r in csv.DictReader(open(csv_path))}
    new = not csv_path.exists()
    f = open(csv_path, "a", newline="")
    w = csv.DictWriter(f, FIELDS)
    if new:
        w.writeheader()
    jobs = [(t, c, rep) for t in TASKS if not a.ids or t["id"] in a.ids
            for c in a.configs for rep in range(a.repeat) if (t["id"], c, rep) not in done]
    print(f"{len(jobs)} runs ({len(done)} already done), workers={a.workers}", flush=True)
    # processes, not threads: OCCT is not guaranteed thread-safe
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, t, c, rep, cfg, out) for t, c, rep in jobs]
        for n, fu in enumerate(as_completed(futs), 1):
            row = fu.result()
            with _lock:
                w.writerow(row); f.flush()
            print(f"[{n}/{len(jobs)}]", row["task"], row["config"], row["rep"],
                  {k: row[k] for k in ("status", "first_pass", "final_pass", "rounds", "l3_errors")}, flush=True)
    f.close()


if __name__ == "__main__":
    main()
