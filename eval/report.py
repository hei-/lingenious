"""python -m eval.report -> eval/results/summary.md + comparison.png (+ by_level.png)"""
import csv
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

import matplotlib.pyplot as plt

# usage: python -m eval.report [results_dir]   (default eval/results; DFM set: eval/results_dfm)
d = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results")
rows = [r for r in csv.DictReader(open(d / "results.csv")) if r["status"] != "error"]
b = lambda s: s == "True"
mean = lambda x: sum(x) / len(x) if x else 0.0


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0, c - h), min(1, c + h)


def agg(sel):
    g = defaultdict(list)
    for r in sel:
        g["first"].append(b(r["first_pass"])); g["final"].append(b(r["final_pass"]))
        g["exec"].append(b(r["exec_ok"])); g["rounds"].append(int(r["rounds"]))
        g["l3"].append(int(r["l3_errors"])); g["disp"].append(int(r["disputes"] or 0))
        g["tok"].append(int(r["prompt_tokens"] or 0) + int(r["completion_tokens"] or 0))
    return g


def pct(xs):
    k, n = sum(xs), len(xs)
    lo, hi = wilson(k, n)
    return f"{k / n:.0%} [{lo:.0%}–{hi:.0%}]" if n else "-"


cfgs = sorted({r["config"] for r in rows})
levels = [l for l in ("easy", "medium", "hard") if any(r["level"] == l for r in rows)]
model = rows[0]["model"] if rows else ""
L = [f"模型:{model};任务数 {len({r['task'] for r in rows})};每格为 通过率 [95% Wilson 区间]\n",
     "## 总体", "| 配置 | 样本 | 执行成功 | 一次通过 | 最终通过 | 平均轮数 | 终稿 L3 error 均值 | 申诉次数 | 平均 token |", "|---|---|---|---|---|---|---|---|---|"]
for c in cfgs:
    g = agg([r for r in rows if r["config"] == c])
    L.append(f"| {c} | {len(g['final'])} | {pct(g['exec'])} | {pct(g['first'])} | {pct(g['final'])} | {mean(g['rounds']):.2f} | {mean(g['l3']):.2f} | {sum(g['disp'])} | {mean(g['tok']):.0f} |")
L += ["", "## 按难度的最终通过率", "| 难度 | " + " | ".join(cfgs) + " |", "|---|" + "---|" * len(cfgs)]
for lv in levels:
    L.append(f"| {lv} | " + " | ".join(pct(agg([r for r in rows if r["config"] == c and r["level"] == lv])["final"]) for c in cfgs) + " |")
L += ["", "## 各任务最终通过次数(通过/总数)", "| 任务 | 难度 | " + " | ".join(cfgs) + " | 常见失败规则(C) |", "|---|---|" + "---|" * len(cfgs) + "---|"]
for t in sorted({(r["task"], r["level"]) for r in rows}, key=lambda x: (levels.index(x[1]), x[0])):
    cells: list = []
    fr: defaultdict = defaultdict(int)
    for c in cfgs:
        sel = [r for r in rows if r["task"] == t[0] and r["config"] == c]
        cells.append(f"{sum(b(r['final_pass']) for r in sel)}/{len(sel)}")
        if c == cfgs[-1]:
            for r in sel:
                for k in filter(None, r["failed_rules"].split(";")):
                    fr[k] += 1
    L.append(f"| {t[0]} | {t[1]} | " + " | ".join(cells) + " | " + ", ".join(f"{k}×{v}" for k, v in sorted(fr.items(), key=lambda kv: -kv[1])[:3]) + " |")
(d / "summary.md").write_text("\n".join(L) + "\n")
print("\n".join(L))

fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, key, title in ((axes[0], "first", "first-try pass"), (axes[1], "final", "final pass")):
    w = 0.8 / max(len(cfgs), 1)
    for ci, c in enumerate(cfgs):
        vals, errs = [], []
        for lv in levels + ["all"]:
            sel = [r for r in rows if r["config"] == c and (lv == "all" or r["level"] == lv)]
            xs = [b(r["first_pass" if key == "first" else "final_pass"]) for r in sel]
            p = mean(xs); lo, hi = wilson(sum(xs), len(xs))
            vals.append(p); errs.append((p - lo, hi - p))
        xpos = [i + (ci - (len(cfgs) - 1) / 2) * w for i in range(len(levels) + 1)]
        ax.bar(xpos, vals, w * 0.9, yerr=list(zip(*errs)), capsize=2, label=f"config {c}")
    ax.set_xticks(range(len(levels) + 1)); ax.set_xticklabels(levels + ["all"]); ax.set_ylim(0, 1.05)
    ax.set_title(title); ax.set_ylabel("pass rate (L1+L2 vs ground truth)")
axes[1].legend(); fig.tight_layout(); fig.savefig(d / "comparison.png", dpi=120)
