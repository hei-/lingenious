"""Config loading: config.yaml plus optional LINGENIOUS__SECTION__KEY=value environment overrides.

Values are parsed as YAML scalars/flows (``3`` -> int, ``0.5`` -> float, ``true`` -> bool, ``[1, 2]`` -> list).
Key segments are matched case-insensitively against existing keys, otherwise lower-cased
(``LINGENIOUS__AGENT__MAX_ROUNDS=3``). Only ``LINGENIOUS__`` (double underscore) names are overrides;
``LINGENIOUS_DATA`` and friends are unrelated runtime variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional, Union

import yaml

PREFIX = "LINGENIOUS__"


def apply_env_overrides(cfg: dict, env: Optional[Mapping[str, str]] = None) -> dict:
    env = os.environ if env is None else env
    for name in sorted(env):
        if not name.startswith(PREFIX):
            continue
        parts = [p for p in name[len(PREFIX):].split("__") if p]
        if not parts:
            continue
        try:
            val = yaml.safe_load(env[name])
        except yaml.YAMLError:
            val = env[name]
        node = cfg
        for i, p in enumerate(parts):
            key = next((k for k in node if isinstance(k, str) and k.lower() == p.lower()), p.lower())
            if i == len(parts) - 1:
                node[key] = val
            else:
                if not isinstance(node.get(key), dict):
                    node[key] = {}
                node = node[key]
    return cfg


def load_config(path: Union[str, Path] = "config.yaml", env: Optional[Mapping[str, str]] = None) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return apply_env_overrides(cfg, env)
