"""Subprocess sandbox for LLM-generated CadQuery scripts.

MVP isolation = static import/call whitelist + child process + timeout + memory cap.
Not suitable for untrusted code in production (use container-level isolation).
"""
from __future__ import annotations

import ast
import json
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ALLOWED_IMPORTS = {"cadquery", "math"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "getattr", "setattr", "delattr", "breakpoint"}


@dataclass
class ExecResult:
    ok: bool
    error: str = ""
    step_path: Optional[Path] = None
    shape: object = None  # cq.Shape, loaded in the parent for checks


def static_check(code: str) -> Optional[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"语法错误: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"禁止导入模块 {a.name}(仅允许 {sorted(ALLOWED_IMPORTS)})"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"禁止导入模块 {node.module}(仅允许 {sorted(ALLOWED_IMPORTS)})"
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"禁止使用 {node.id}"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"禁止访问属性 {node.attr}"
    return None


def _limits(mem_mb: int):
    def f():
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
    return f


def execute(code: str, workdir: Optional[Path] = None, timeout_s: int = 60, mem_mb: int = 4096) -> ExecResult:
    err = static_check(code)
    if err:
        return ExecResult(False, err)
    workdir = Path(workdir or tempfile.mkdtemp(prefix="cad_")).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    script, step = workdir / "script.py", workdir / "part.step"
    script.write_text(code)
    if step.exists():
        step.unlink()
    try:
        p = subprocess.run(
            [sys.executable, "-m", "core.sandbox.runner", str(script), str(step)],
            capture_output=True, text=True, timeout=timeout_s, cwd=workdir,
            env={"PATH": "/usr/local/bin:/usr/bin", "PYTHONPATH": str(Path(__file__).resolve().parents[2]), "HOME": str(workdir)},
            preexec_fn=_limits(mem_mb),
        )
    except subprocess.TimeoutExpired:
        return ExecResult(False, f"脚本执行超过 {timeout_s}s 超时")
    last = (p.stdout.strip().splitlines() or [""])[-1]
    try:
        info = json.loads(last)
    except json.JSONDecodeError:
        return ExecResult(False, (p.stderr or p.stdout)[-800:] or "脚本异常退出(可能超出内存限制)")
    if not info.get("ok"):
        return ExecResult(False, info.get("error", "未知错误"))
    import cadquery as cq
    shape = cq.importers.importStep(str(step)).val()
    return ExecResult(True, step_path=step, shape=shape)
