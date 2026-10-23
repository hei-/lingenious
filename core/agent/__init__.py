"""Agent loop: parse -> generate -> execute -> check -> fix. LLM designs; geometry code judges."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.llm import LLM, extract_code
from core.models import Assertions, Issue, PartSpec
from core.sandbox import ExecResult, execute
from core.agent import prompts

# Eval configs: which check levels feed back into the loop.
CONFIG_LEVELS = {"A": (), "B": ("L1", "L2"), "C": ("L1", "L2", "L3")}


@dataclass
class Round:
    n: int
    code: str
    issues: list[Issue]
    seconds: float


@dataclass
class RunResult:
    status: str  # success | need_info | failed
    spec: Optional[PartSpec] = None
    code: str = ""
    exec: Optional[ExecResult] = None
    rounds: list[Round] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)  # final (warnings on success)
    usage: dict = field(default_factory=dict)

    def log_text(self) -> str:
        lines = []
        for r in self.rounds:
            errs = [i for i in r.issues if i.severity == "error"]
            if errs:
                lines.append(f"第{r.n}轮:未通过 " + " ".join(f"[{i.rule}] {i.message}" for i in errs))
            else:
                lines.append(f"第{r.n}轮:通过")
        return "\n".join(lines)


def parse_spec(llm: LLM, request: str, material: str = "", process: str = "") -> PartSpec:
    extra = f"\n材料:{material}" if material else ""
    extra += f"\n工艺:{process}" if process else ""
    spec = llm.structured(
        [{"role": "system", "content": prompts.SPEC_SYSTEM}, {"role": "user", "content": request + extra}],
        PartSpec,
    )
    return _demote_defaultable(spec)


# Details that always have a sensible default; the LLM sometimes lists them as missing anyway.
DEFAULTABLE = ("位置", "孔位", "圆角", "倒角", "孔深")


def _demote_defaultable(spec: PartSpec) -> PartSpec:
    keep = [m for m in spec.missing if not any(k in m for k in DEFAULTABLE)]
    moved = [f"未给出:{m},按默认处理" for m in spec.missing if m not in keep]
    return spec.model_copy(update={"missing": keep, "defaults_used": spec.defaults_used + moved}) if moved else spec


def _issues_text(issues: list[Issue], limit: int = 8) -> str:
    ordered = sorted(issues, key=lambda i: i.severity != "error")[:limit]
    return "\n".join(
        f"- [{i.rule}] {i.message}" + (f"(建议:{i.hint})" if i.hint else "") for i in ordered
    )


def _constraints_text(spec: PartSpec) -> str:
    """Spec-derived invariants handed back with L3 violations so DFM fixes do not drift from the request."""
    a = spec.assertions
    lines = []
    if a.bbox:
        lines.append(f"- 包围盒 {a.bbox.x:g}×{a.bbox.y:g}×{a.bbox.z:g} mm")
    if a.hole_count is not None:
        lines.append(f"- 孔数 {a.hole_count}")
    if a.hole_diameters:
        lines.append("- 孔径(mm)" + "、".join(f"Ø{d:g}" for d in a.hole_diameters))
    for h in a.hole_positions:
        lines.append(f"- 孔位 {h.model_dump(exclude_none=True)}")
    return "\n".join(lines)


DISPUTABLE = {"bbox_match", "hole_count", "hole_diameter", "hole_position", "volume_range"}


def _apply_disputes(code: str, issues: list[Issue]) -> list[Issue]:
    """L2 assertions are LLM-derived and can be wrong: let the script dispute them (demoted to warning, logged)."""
    disputed = set(re.findall(r"#\s*ASSERTION_DISPUTE:\s*(\w+)", code)) & DISPUTABLE
    out = []
    for i in issues:
        if i.rule in disputed and i.severity == "error":
            i = i.model_copy(update={"severity": "warning", "message": "[脚本申诉,以原始需求为准] " + i.message})
        out.append(i)
    return out


def _check(res: ExecResult, spec: PartSpec, cfg: dict, levels: tuple) -> list[Issue]:
    if not res.ok:
        return [Issue(rule="exec_error", level="L0", message=f"脚本执行失败:{res.error}")]
    if not levels:
        return []
    from core.checks import run_checks  # imported lazily: heavy + written separately
    return run_checks(res.shape, spec, cfg, levels=levels)


def _loop(llm: LLM, code: str, spec: PartSpec, cfg: dict, levels: tuple, workdir: Path, round0: int = 1, request: str = "", on_event=None) -> RunResult:
    emit = on_event or (lambda *_: None)
    max_rounds = cfg["agent"]["max_rounds"]
    out = RunResult(status="failed", spec=spec, code=code)
    prev_sig = None
    for n in range(round0, round0 + max_rounds):
        t0 = time.time()
        res = execute(code, workdir=workdir / f"round{n}", timeout_s=cfg["sandbox"]["timeout_s"], mem_mb=cfg["sandbox"].get("mem_mb", 4096))
        issues = _apply_disputes(code, _check(res, spec, cfg, levels))
        out.rounds.append(Round(n, code, issues, time.time() - t0))
        emit("round", {"n": n, "seconds": round(time.time() - t0, 2), "exec_ok": res.ok,
                       "issues": [i.model_dump() for i in issues]})
        out.code, out.exec, out.issues = code, res, issues
        errors = [i for i in issues if i.severity == "error"]
        if not errors:
            out.status = "success"
            break
        sig = (code, tuple(i.rule for i in errors))
        if sig == prev_sig or n == round0 + max_rounds - 1:
            break
        prev_sig = sig
        emit("fixing", {"n": n})
        code = extract_code(llm.chat([
            {"role": "system", "content": prompts.SYSTEM},
            {"role": "user", "content": prompts.fix_user(code, _issues_text(issues), request, _constraints_text(spec) if "L3" in levels else "")},
        ]))
    out.usage = dict(llm.usage)
    return out


def run(llm: LLM, request: str, cfg: dict, workdir: Path, config: str = "C", material: str = "", process: str = "", on_event=None) -> RunResult:
    emit = on_event or (lambda *_: None)
    levels = CONFIG_LEVELS[config]
    emit("parsing", {})
    spec = parse_spec(llm, request, material, process)
    emit("spec", spec.model_dump())
    if spec.missing:
        return RunResult(status="need_info", spec=spec, usage=dict(llm.usage))
    emit("generating", {})
    code = extract_code(llm.chat([
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.generate_user(spec.model_dump_json(indent=1), request)},
    ]))
    return _loop(llm, code, spec, cfg, levels, workdir, request=request, on_event=on_event)


def update_spec(llm: LLM, spec: PartSpec, change: str) -> PartSpec:
    """Carry the spec (and so the L2 assertions) through a follow-up change instead of dropping it.
    If the LLM cannot produce a valid spec, fall back to no dimension assertions (L1 + L3 still run)."""
    try:
        new = llm.structured(
            [{"role": "system", "content": prompts.SPEC_UPDATE_SYSTEM},
             {"role": "user", "content": prompts.update_spec_user(spec.model_dump_json(indent=1), change)}],
            PartSpec,
        )
    except ValueError:
        new = spec.model_copy(deep=True, update={"assertions": Assertions()})
        new.defaults_used = new.defaults_used + [f"修改后规格更新失败,本版不校验尺寸断言:{change}"]
    return new.model_copy(update={"missing": []})


def modify(llm: LLM, prev: RunResult, change: str, cfg: dict, workdir: Path, config: str = "C", on_event=None) -> RunResult:
    emit = on_event or (lambda *_: None)
    assert prev.spec is not None, "modify() needs a previous spec"
    emit("parsing", {})
    spec = update_spec(llm, prev.spec, change)
    emit("spec", spec.model_dump())
    emit("generating", {})
    code = extract_code(llm.chat([
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.modify_user(prev.code, change)},
    ]))
    return _loop(llm, code, spec, cfg, CONFIG_LEVELS[config], workdir, round0=len(prev.rounds) + 1,
                 request=f"(在上一版基础上的修改){change}", on_event=on_event)


def save(result: RunResult, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "part.py").write_text(result.code)
    if result.exec and result.exec.ok and result.exec.step_path:
        (out / "part.step").write_bytes(Path(result.exec.step_path).read_bytes())
    (out / "run.json").write_text(json.dumps({
        "status": result.status,
        "spec": result.spec.model_dump() if result.spec else None,
        "rounds": [{"n": r.n, "seconds": round(r.seconds, 2), "code": r.code,
                    "issues": [i.model_dump() for i in r.issues]} for r in result.rounds],
        "final_issues": [i.model_dump() for i in result.issues],
        "usage": result.usage,
    }, ensure_ascii=False, indent=2))
    (out / "log.txt").write_text(result.log_text())
