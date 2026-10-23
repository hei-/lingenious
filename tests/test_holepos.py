import cadquery as cq

from core.checks import run_checks
from core.checks.l2 import hole_position
from core.models import Assertions, HolePos, PartSpec

H5_WANT = [HolePos(diameter=10, x=-25, y=0), HolePos(diameter=8, x=25, y=14), HolePos(diameter=8, x=25, y=-14)]


def spec(*hp, **kw):
    return PartSpec(assertions=Assertions(hole_positions=list(hp), **kw))


def check(shape, *hp):
    return hole_position.check(shape, spec(*hp), {})


def h5_body():
    base = cq.Workplane("XY").box(100, 50, 10, centered=(True, True, False))
    up = cq.Workplane("XY").box(50, 50, 10, centered=(False, True, False)).translate((-50, 0, 10))
    return base.union(up)


def h5_good():
    cut = (cq.Workplane("XY").pushPoints([(-25, 0)]).circle(5).extrude(20)
           .union(cq.Workplane("XY").pushPoints([(25, 14), (25, -14)]).circle(4).extrude(10)))
    return h5_body().cut(cut).val()


def h5_bad():
    """Real failure: workplane origin moved onto the upper tier's top face before drilling."""
    b = h5_body()
    for x, y, d in [(-25, 0, 10), (25, 14, 8), (25, -14, 8)]:
        b = b.faces(">Z").workplane(centerOption="CenterOfBoundBox").pushPoints([(x, y)]).hole(d)
    return b.val()


def test_good_h5_passes():
    assert check(h5_good(), *H5_WANT) == []


def test_origin_independent_translation():
    s = h5_good().moved(cq.Location(cq.Vector(300, -70, 40)))
    assert check(s, *H5_WANT) == []


def test_bad_h5_fails_with_numbers():
    iss = check(h5_bad(), *H5_WANT)
    assert iss and all(i.rule == "hole_position" for i in iss)
    assert any("Ø8" in i.message and "偏差" in i.message for i in iss)
    assert "绝对坐标" in iss[0].hint


def test_missing_hole_and_wrong_axis():
    s = h5_good()
    assert check(s, HolePos(diameter=6, x=0, y=0))[0].message.startswith("未找到")
    assert check(s, HolePos(diameter=10, axis="X", y=0, z=5))


def test_tolerance_and_partial_coords():
    s = h5_good()
    assert check(s, HolePos(diameter=10, x=-24.5)) == []          # y unconstrained
    assert check(s, HolePos(diameter=10, x=-22, tol=1.0))
    assert check(s, HolePos(diameter=10, x=-22, tol=3.0)) == []


def test_multiset_matching_not_double_counted():
    s = h5_good()
    # two expectations for the single d10 hole: second one cannot be matched
    assert len(check(s, HolePos(diameter=10, x=-25, y=0), HolePos(diameter=10, x=-25, y=0))) == 1


def test_empty_is_skipped_and_registered():
    assert check(h5_good()) == []
    iss = run_checks(h5_bad(), spec(*H5_WANT), {}, levels=("L2",))
    assert any(i.rule == "hole_position" for i in iss)


def test_dispute_demotes():
    from core.agent import DISPUTABLE, _apply_disputes
    assert "hole_position" in DISPUTABLE
    iss = check(h5_bad(), *H5_WANT)
    out = _apply_disputes("# ASSERTION_DISPUTE: hole_position\n", iss)
    assert all(i.severity == "warning" for i in out)
