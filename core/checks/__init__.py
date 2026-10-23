"""Geometry checks: run_checks(shape, spec, cfg, levels) -> list[Issue]."""
from __future__ import annotations

import cadquery as cq

from core.models import Issue
from .base import Rule, rule_enabled
from .l1 import positive_volume, single_solid, valid_solid
from .l2 import bbox_match, hole_count, hole_breakout, hole_diameter, hole_position, volume_range
from .l3 import (deep_pocket, hole_depth_ratio, hole_edge_distance_rule, hole_spacing,
                 internal_corner_radius, min_wall_thickness, thin_web_height)
from .features import Hole, find_holes

L1_RULES = [valid_solid, single_solid, positive_volume]
L2_RULES = [bbox_match, hole_count, hole_diameter, hole_position, volume_range, hole_breakout]
L3_RULES = [hole_edge_distance_rule, internal_corner_radius, min_wall_thickness, hole_spacing,
            hole_depth_ratio, deep_pocket, thin_web_height]
ALL_RULES = {"L1": L1_RULES, "L2": L2_RULES, "L3": L3_RULES}

__all__ = ["run_checks", "ALL_RULES", "Rule", "Hole", "find_holes"]


def _to_shape(obj):
    if isinstance(obj, cq.Workplane):
        vals = obj.vals()
        if len(vals) == 1:
            return vals[0]
        return cq.Compound.makeCompound([v for v in vals if isinstance(v, cq.Shape)])
    return obj


def run_checks(shape, spec, cfg, levels=("L1", "L2", "L3")) -> list[Issue]:
    shape = _to_shape(shape)
    cfg = cfg or {}
    issues: list[Issue] = []
    for lvl in ("L1", "L2", "L3"):
        if lvl not in levels:
            continue
        lvl_issues: list[Issue] = []
        for r in ALL_RULES[lvl]:
            if not rule_enabled(cfg, r.id):
                continue
            try:
                lvl_issues += r.check(shape, spec, cfg)
            except Exception as e:  # a broken rule must not crash the agent loop
                if lvl == "L1":
                    lvl_issues.append(Issue(rule=r.id, level="L1", message=f"规则 {r.id} 执行异常: {e!r}",
                                            hint="几何可能严重损坏,重新建模"))
                # L2/L3 internal errors are swallowed as they are approximations
        issues += lvl_issues
        if lvl == "L1" and any(i.severity == "error" for i in lvl_issues):
            break  # invalid geometry: later levels are meaningless
    return issues
