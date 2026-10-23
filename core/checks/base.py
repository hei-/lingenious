"""Rule base: each rule is a small object with id, level and check()."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.models import Issue

DEFAULTS = {
    "hole_edge_factor": 1.5,
    "min_wall_error": 1.5,
    "min_wall_warn": 2.0,
    "min_internal_radius": 0.5,
    "recommended_internal_radius": 3.0,
    "hole_spacing_factor": 1.0,
    "hole_edge_wall_cap": 6.0,
    # hole_depth_ratio: blind hole depth/diameter; through holes (plate thickness/diameter) only warn
    "hole_depth_warn": 6.0,
    "hole_depth_error": 10.0,
    "hole_depth_through_warn": 6.0,
    # deep_pocket: closed pocket depth / smallest pocket width
    "deep_pocket_warn": 4.0,
    # thin_web_height: rib/web height / thickness, only for webs thinner than the max thickness (mm)
    "thin_web_warn": 8.0,
    "thin_web_max_thickness": 5.0,
}

# dfm.rules.<rule id>.<key> -> DEFAULTS key (explicit per-rule overrides)
RULE_KEYS = {
    "hole_edge_distance": {"factor": "hole_edge_factor"},
    "internal_corner_radius": {"min_radius": "min_internal_radius", "recommended": "recommended_internal_radius"},
    "hole_depth_ratio": {"warn": "hole_depth_warn", "error": "hole_depth_error",
                         "through_warn": "hole_depth_through_warn"},
    "deep_pocket": {"warn": "deep_pocket_warn"},
    "thin_web_height": {"warn": "thin_web_warn", "max_thickness": "thin_web_max_thickness"},
}


def dfm_cfg(cfg, spec=None) -> dict:
    """Merge defaults, cfg['dfm'] and (docs-style) material overrides."""
    out = dict(DEFAULTS)
    d = (cfg or {}).get("dfm") or {}
    out.update({k: v for k, v in d.items() if k in DEFAULTS and v is not None})
    rules = d.get("rules") or {}
    for rid, keys in RULE_KEYS.items():
        rc = rules.get(rid) or {}
        for k, target in keys.items():
            if rc.get(k) is not None:
                out[target] = rc[k]
    if spec is not None:
        # precedence (low -> high): DEFAULTS < dfm.* < dfm.rules.* < material_overrides < process_overrides
        for table, key in (("material_overrides", "material"), ("process_overrides", "process")):
            ov = (d.get(table) or {}).get(str(getattr(spec, key, None))) or {}
            if ov.get("min_wall_thickness") is not None:
                out["min_wall_error"] = ov["min_wall_thickness"]
                out["min_wall_warn"] = max(out["min_wall_warn"], ov["min_wall_thickness"])
            for k, v in ov.items():
                if k in DEFAULTS and v is not None:
                    out[k] = v
    return out


def rule_enabled(cfg, rule_id: str) -> bool:
    rules = ((cfg or {}).get("dfm") or {}).get("rules") or {}
    return bool((rules.get(rule_id) or {}).get("enabled", True))


@dataclass
class Rule:
    id: str
    level: str
    fn: Callable  # fn(shape, spec, dfm_cfg) -> list[Issue]

    def check(self, shape, spec, cfg) -> list[Issue]:
        return self.fn(shape, spec, dfm_cfg(cfg, spec))


def rule(id: str, level: str):
    def deco(fn):
        return Rule(id, level, fn)
    return deco
