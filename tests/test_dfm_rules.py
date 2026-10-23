"""Tests for hole_depth_ratio, deep_pocket, thin_web_height (+ no-error sweep over eval/refs)."""
from pathlib import Path

import cadquery as cq
import pytest

from core.checks.base import dfm_cfg
from core.checks import l3
from core.models import PartSpec
from core.sandbox import execute

RULES = {"hole_depth_ratio": l3.hole_depth_ratio, "deep_pocket": l3.deep_pocket,
         "thin_web_height": l3.thin_web_height}
REFS = sorted(Path(__file__).resolve().parents[1].glob("eval/refs/*.py"))


def run(rid, shape, cfg=None, **spec_kw):
    return RULES[rid].check(shape, PartSpec(**spec_kw), cfg or {})


def block(l=60, w=40, t=30):
    return cq.Workplane("XY").box(l, w, t)


# ---- hole_depth_ratio
def test_blind_hole_error_and_ok():
    deep = block().faces(">Z").workplane().hole(4, 25).val()      # ratio 6.25 -> warn
    assert [i.severity for i in run("hole_depth_ratio", deep)] == ["warning"]
    very = block().faces(">Z").workplane().hole(2, 25).val()      # 12.5 -> error
    assert [i.severity for i in run("hole_depth_ratio", very)] == ["error"]
    ok = block().faces(">Z").workplane().hole(8, 20).val()
    assert run("hole_depth_ratio", ok) == []


def test_through_hole_only_warns():
    s = block(t=40).faces(">Z").workplane().hole(2).val()         # 20:1 through
    iss = run("hole_depth_ratio", s)
    assert iss and all(i.severity == "warning" for i in iss)
    assert run("hole_depth_ratio", block(t=10).faces(">Z").workplane().hole(5).val()) == []


def test_hole_depth_config_and_material_override():
    s = block().faces(">Z").workplane().hole(5, 25).val()         # ratio 5
    assert run("hole_depth_ratio", s) == []
    cfg = {"dfm": {"material_overrides": {"steel": {"hole_depth_warn": 4}}}}
    assert len(run("hole_depth_ratio", s, cfg, material="steel")) == 1
    cfg2 = {"dfm": {"rules": {"hole_depth_ratio": {"warn": 4}}}}
    assert len(run("hole_depth_ratio", s, cfg2)) == 1
    assert dfm_cfg(cfg2)["hole_depth_warn"] == 4


# ---- deep_pocket
def test_deep_pocket():
    deep = block(60, 40, 40).faces(">Z").workplane().rect(6, 30).cutBlind(-30).val()   # 30/6
    iss = run("deep_pocket", deep)
    assert iss and iss[0].severity == "warning" and "深" in iss[0].message
    shallow = block().faces(">Z").workplane().rect(30, 20).cutBlind(-8).val()
    assert run("deep_pocket", shallow) == []
    assert run("deep_pocket", block().val()) == []


# ---- thin_web_height
def test_thin_web():
    base = cq.Workplane("XY").box(60, 40, 8, centered=(True, True, False))
    rib = cq.Workplane("XY").box(60, 2, 30, centered=(True, True, False)).translate((0, 0, 8))
    iss = run("thin_web_height", base.union(rib).val())
    assert iss and iss[0].severity == "warning"
    rib2 = cq.Workplane("XY").box(60, 4, 20, centered=(True, True, False)).translate((0, 0, 8))
    assert run("thin_web_height", base.union(rib2).val()) == []
    assert run("thin_web_height", block().val()) == []


def test_rule_disable_and_garbage_input():
    from core.checks.base import rule_enabled
    cfg = {"dfm": {"rules": {"deep_pocket": {"enabled": False}}}}
    assert not rule_enabled(cfg, "deep_pocket") and rule_enabled(cfg, "thin_web_height")
    for r in RULES.values():
        assert r.check(cq.Workplane("XY").sphere(5).val(), PartSpec(), {}) == []


@pytest.mark.parametrize("ref", REFS, ids=[p.stem for p in REFS])
def test_no_errors_on_reference_solids(ref):
    res = execute(ref.read_text())
    assert res.ok, res.error
    for rid, r in RULES.items():
        bad = [i for i in r.check(res.shape, PartSpec(), {}) if i.severity == "error"]
        assert not bad, (rid, bad)
