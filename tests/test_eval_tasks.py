import json
from pathlib import Path

import cadquery as cq
import pytest
import yaml

from core.checks import run_checks
from core.models import Assertions, PartSpec
from eval.build_truth import REFS, build_ref, derive
from eval.tasks import _SPECS, TASKS

CFG = yaml.safe_load(open(Path(__file__).parents[1] / "config.yaml"))
IDS = [t["id"] for t in TASKS]
_shapes: dict = {}


def shape(tid):
    if tid not in _shapes:
        _shapes[tid] = build_ref(tid)
    return _shapes[tid]


def spec_of(truth):
    return PartSpec(assertions=Assertions.model_validate(truth))


def errors(issues):
    return [i for i in issues if i.severity == "error"]


def test_inventory():
    assert len(TASKS) == len(_SPECS) >= 20
    assert len(set(IDS)) == len(IDS)
    assert {"e1", "e2", "e3", "e4", "m1", "m2", "m3", "m4", "h1", "h2"} <= set(IDS)
    lv = [t["level"] for t in TASKS]
    assert set(lv) == {"easy", "medium", "hard"}
    assert all(lv.count(k) >= 4 for k in ("easy", "medium", "hard"))
    assert sorted(p.stem for p in REFS.glob("*.py")) == sorted(IDS)
    for t in TASKS:
        assert t["text"].strip()
        a = Assertions.model_validate(t["truth"])
        assert a.bbox and a.hole_count == len(a.hole_diameters) and a.volume_range
        assert a.volume_range[0] < a.volume_range[1]


@pytest.mark.parametrize("tid", IDS)
def test_reference_matches_truth_and_is_dfm_clean(tid):
    truth = next(t["truth"] for t in TASKS if t["id"] == tid)
    s = shape(tid)
    assert truth == json.loads(json.dumps(derive(s)))        # truth.json is up to date
    issues = run_checks(s, spec_of(truth), CFG, levels=("L1", "L2", "L3"))
    assert errors(issues) == [], [i.message for i in errors(issues)]


@pytest.mark.parametrize("tid", IDS)
def test_truth_discriminates(tid):
    t = next(t for t in TASKS if t["id"] == tid)
    truth = t["truth"]
    sp = spec_of(truth)
    b = truth["bbox"]
    # right bbox, wrong content: solid block, volume way off for any part with material removed
    blank = cq.Workplane("XY").box(b["x"], b["y"], b["z"]).val()
    rules = {i.rule for i in errors(run_checks(blank, sp, CFG, levels=("L1", "L2")))}
    if truth["hole_count"]:
        assert "hole_count" in rules and "hole_diameter" in rules
    # wrong bbox
    wrong = cq.Workplane("XY").box(b["x"] * 1.3, b["y"], b["z"]).val()
    assert "bbox_match" in {i.rule for i in errors(run_checks(wrong, sp, CFG, levels=("L2",)))}
    # volume window is tight enough to reject the full block when material was removed
    lo, hi = truth["volume_range"]
    if blank.Volume() > hi:
        assert "volume_range" in rules
