#!/usr/bin/env python3
"""Tiny secret scan (pre-commit hook / manual). Never prints the secret itself, only file:line and the rule.

usage: scripts/scan_secrets.py [files...]     (no args: scan the whole tree, skipping .git, node_modules, out, data, .env)
"""
import re
import sys
from pathlib import Path

RULES = {
    "openai/deepseek-style key (sk-...)": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "DEEPSEEK_API_KEY with a value": re.compile(r"DEEPSEEK_API_KEY\s*[=:]\s*[\"']?(?!\s*$)(?![\"']?\s*$)(?!\$|<|your|xxx|changeme)[A-Za-z0-9_-]{8,}", re.I),
    "Feishu/Lark app secret or token": re.compile(
        r"(app_secret|tenant_access_token|user_access_token|verification_token|encrypt_key)[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9_-]{16,}", re.I),
    "Feishu/Lark raw token (t-/u-)": re.compile(r"\b[tu]-[a-f0-9]{30,}\b"),
    "private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", "node_modules", "out", "data", ".ruff_cache", ".mypy_cache", ".pytest_cache", "dist", "__pycache__"}
SKIP_NAMES = {".env", "scan_secrets.py", "package-lock.json"}
SKIP_SUFFIX = {".lock", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".step", ".stl", ".glb", ".woff", ".woff2", ".ttf", ".ico", ".zip"}


def walk():
    for p in Path(".").rglob("*"):
        if p.is_file() and not (set(p.parts) & SKIP_DIRS) and p.name not in SKIP_NAMES and p.suffix not in SKIP_SUFFIX:
            yield p


def main(argv):
    files = [Path(a) for a in argv if Path(a).name not in SKIP_NAMES] if argv else walk()
    hits = 0
    for p in files:
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for name, rx in RULES.items():
                if rx.search(line):
                    print(f"{p}:{n}: possible secret: {name}")
                    hits += 1
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
