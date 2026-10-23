"""Thin lark-cli wrapper (I/O layer). Never logs secrets."""
from __future__ import annotations

import json
import subprocess
from typing import Any, List, Optional

LARK = "lark-cli"


class LarkError(RuntimeError):
    pass


def run(args: List[str], timeout: int = 300, cwd: Optional[str] = None) -> Any:
    p = subprocess.run([LARK] + args + ["--as", "user"], capture_output=True, text=True, timeout=timeout, cwd=cwd)
    out = p.stdout.strip()
    try:
        data = json.loads(out) if out else None
    except ValueError:
        data = None
    if p.returncode != 0 or (isinstance(data, dict) and data.get("ok") is False):
        raise LarkError("lark-cli %s failed: %s" % (" ".join(args[:2]), (out or p.stderr)[:600]))
    return data if data is not None else out
