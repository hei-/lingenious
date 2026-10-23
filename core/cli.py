"""CLI: python -m core.cli "需求" --out out/run1 [--config C] [--modify "立板厚度改4mm"]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


from core import agent
from core.config import load_config
from core.llm import LLM


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--out", default="out/run")
    ap.add_argument("--config", default="C", choices=["A", "B", "C"])
    ap.add_argument("--material", default="")
    ap.add_argument("--modify", action="append", default=[], help="可多次,依次基于上一版修改")
    ap.add_argument("--cfg", default="config.yaml")
    a = ap.parse_args(argv)

    cfg = load_config(a.cfg)
    llm = LLM(cfg)
    out = Path(a.out)
    res = agent.run(llm, a.request, cfg, out / "v1", a.config, material=a.material)
    _report(res, out / "v1", 1)
    for i, change in enumerate(a.modify, start=2):
        if res.status != "success":
            break
        res = agent.modify(llm, res, change, cfg, out / f"v{i}", a.config)
        _report(res, out / f"v{i}", i)
    return 0 if res.status == "success" else 1


def _report(res, out: Path, version: int) -> None:
    print(f"\n=== v{version}: {res.status} ===")
    if res.status == "need_info":
        print("需补充:", "; ".join(res.spec.missing))
        return
    print(res.log_text())
    for i in res.issues:
        print(f"  ({i.severity}) [{i.rule}] {i.message}")
    agent.save(res, out)
    if res.exec and res.exec.ok:
        from core.render import render
        render(res.exec.shape, out / "render.png", title=f"v{version} {res.spec.part_type}")
        try:
            from core.drawing import draw
            info = draw(res.exec.shape, out, name=res.spec.part_type, material=res.spec.material)
            print(f"工程图: {Path(info['pdf']).name}, {Path(info['dxf']).name}(孔 {info['holes']} 个,HLR={info['hlr']})")
        except Exception as e:  # drawing is a bonus deliverable; never fail the run for it
            print(f"工程图生成失败(已跳过): {e}")
    print(f"输出目录: {out}  tokens: {res.usage}")


if __name__ == "__main__":
    sys.exit(main())
