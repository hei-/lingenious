import json
from pathlib import Path

import pytest
import yaml

from core.checks import run_checks
from core.models import Assertions, PartSpec
from eval.build_truth import derive
from eval.build_truth_dfm import REFS, build_ref
from eval.tasks_dfm import DFM_RULES, TASKS, _SPECS

CFG = yaml.safe_load(open(Path(__file__).parents[1] / "config.yaml"))
IDS = [t["id"] for t in TASKS]
EXISTING_L3 = {"hole_edge_distance", "internal_corner_radius", "min_wall_thickness", "hole_spacing"}
_shapes: dict = {}


def shape(name):
    if name not in _shapes:
        _shapes[name] = build_ref(name)
    return _shapes[name]


def spec_of(truth):
    return PartSpec(assertions=Assertions.model_validate(truth))


def errors(issues):
    return [i for i in issues if i.severity == "error"]


def test_inventory():
    assert IDS == [f"d{i}" for i in range(1, 13)] == [s[0] for s in _SPECS]
    assert set(DFM_RULES) == set(IDS)
    for t in TASKS:
        a = Assertions.model_validate(t["truth"])
        assert a.bbox and a.hole_count == len(a.hole_diameters) and a.volume_range
        for w in ("圆角", "倒角", "最小壁厚", "边距"):
            assert w not in t["text"]
    names = sorted(p.stem for p in REFS.glob("*.py"))
    assert names == sorted(IDS + [i + "_naive" for i in IDS])


@pytest.mark.parametrize("tid", IDS)
def test_clean_reference_matches_truth_and_is_clean(tid):
    truth = next(t["truth"] for t in TASKS if t["id"] == tid)
    s = shape(tid)
    assert truth == json.loads(json.dumps(derive(s)))
    issues = run_checks(s, spec_of(truth), CFG, levels=("L1", "L2", "L3"))
    assert errors(issues) == [], [i.message for i in errors(issues)]


@pytest.mark.parametrize("tid", IDS)
def test_naive_reference_violates_dfm_but_passes_l1_l2(tid):
    truth = next(t["truth"] for t in TASKS if t["id"] == tid)
    s = shape(tid + "_naive")
    sp = spec_of(truth)
    assert errors(run_checks(s, sp, CFG, levels=("L1", "L2"))) == []
    l3 = errors(run_checks(s, sp, CFG, levels=("L3",)))
    rules = {i.rule for i in l3} & EXISTING_L3
    assert rules, "naive reading must violate an existing L3 rule"
    assert rules & set(DFM_RULES[tid]), (rules, DFM_RULES[tid])
