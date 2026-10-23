import cadquery as cq

from core.checks import ALL_RULES, find_holes, run_checks
from core.models import Assertions, BBox, PartSpec

CFG = {"dfm": {"hole_edge_factor": 1.5, "min_wall_error": 1.5, "min_wall_warn": 2.0,
               "min_internal_radius": 0.5, "recommended_internal_radius": 3.0}}


def spec(**kw):
    return PartSpec(assertions=Assertions(**kw))


def rules(issues, rid=None, sev=None):
    return [i for i in issues if (rid is None or i.rule == rid) and (sev is None or i.severity == sev)]


def run_rule(rid, shape, sp=None, cfg=CFG):
    for lvl in ALL_RULES.values():
        for r in lvl:
            if r.id == rid:
                return r.check(shape, sp or spec(), cfg)
    raise KeyError(rid)


def plate(l=100, w=60, t=10):
    return cq.Workplane("XY").box(l, w, t).val()


def plate_holes(pts, d, l=100, w=60, t=10):
    return cq.Workplane("XY").box(l, w, t).faces(">Z").workplane().pushPoints(pts).hole(d).val()


def bracket(bad: bool, wall_h=70):
    """Base 100x60x6, wall (wall_h high, 3 thick) along the long edge y=-30, 4x d6.6 + 1x d20 wall hole."""
    base = cq.Workplane("XY").box(100, 60, 6, centered=(True, True, False))
    wall = cq.Workplane("XY").box(100, 3, wall_h, centered=(True, False, False)).translate((0, -30, 0))
    body = base.union(wall)
    if not bad:
        body = body.edges(cq.selectors.BoxSelector((-60, -28, 5), (60, -26, 7))).fillet(3)
    ex, ey = (3.5, 3.5) if bad else (12, 12)
    # holes through the base only; the two near the wall are kept clear of the wall (y > -27)
    pts = [(50 - ex, 30 - ey), (-50 + ex, 30 - ey), (50 - ex, -20), (-50 + ex, -20)]
    if not bad:
        pts = [(50 - ex, 30 - ey), (-50 + ex, 30 - ey), (50 - ex, -15), (-50 + ex, -15)]
    for x, y in pts:
        body = body.cut(cq.Workplane("XY").circle(3.3).extrude(10).translate((x, y, -2)))
    hole = cq.Workplane("XZ").center(0, wall_h / 2 + 3).circle(10).extrude(10).translate((0, -20, 0))
    body = body.cut(hole)
    return body.val()


# ---------------------------------------------------------------- features

def test_find_holes_through_and_blind():
    s = (cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane()
         .pushPoints([(-10, 0)]).hole(5).pushPoints([(10, 0)]).hole(4, 6).val())
    hs = find_holes(s)
    assert len(hs) == 2
    by = {round(h.diameter, 2): h for h in hs}
    assert by[5.0].through and abs(by[5.0].depth - 10) < 1e-6
    assert not by[4.0].through and abs(by[4.0].depth - 6) < 1e-6


def test_find_holes_ignores_outer_cylinder_and_fillet():
    cyl = cq.Workplane("XY").circle(10).extrude(20).val()
    assert find_holes(cyl) == []
    filleted = cq.Workplane("XY").box(20, 20, 20).edges("|Z").fillet(3).val()
    assert find_holes(filleted) == []


def test_find_holes_merges_split_faces():
    # hole whose wall is split by a seam / pocket: union of two stacked plates with same bore
    a = cq.Workplane("XY").box(30, 30, 5, centered=(True, True, False)).faces(">Z").workplane().hole(6)
    b = cq.Workplane("XY").box(30, 30, 5, centered=(True, True, False)).translate((0, 0, 5)).faces(">Z").workplane().hole(6)
    s = a.union(b, clean=False).val()
    hs = find_holes(s)
    assert len(hs) == 1 and abs(hs[0].depth - 10) < 1e-6 and hs[0].through


# ---------------------------------------------------------------------- L1

def test_valid_solid():
    assert run_rule("valid_solid", plate()) == []
    # open shell is not a valid closed solid
    bad = cq.Compound.makeCompound([cq.Workplane("XY").rect(10, 10).extrude(1).faces(">Z").val()])
    out = run_rule("valid_solid", bad) + run_rule("single_solid", bad)
    assert out


def test_single_solid():
    assert run_rule("single_solid", plate()) == []
    two = cq.Compound.makeCompound([plate(), plate().moved(cq.Location(cq.Vector(200, 0, 0)))])
    out = run_rule("single_solid", two)
    assert out and out[0].measured == 2 and "2" in out[0].message


def test_positive_volume():
    assert run_rule("positive_volume", plate()) == []
    empty = cq.Compound.makeCompound([])
    out = run_rule("positive_volume", empty)
    assert out and out[0].level == "L1"


def test_l1_short_circuits():
    two = cq.Compound.makeCompound([plate(), plate().moved(cq.Location(cq.Vector(200, 0, 0)))])
    sp = spec(hole_count=3)
    out = run_checks(two, sp, CFG)
    assert out and all(i.level == "L1" for i in out)


# ---------------------------------------------------------------------- L2

def test_bbox_match():
    s = plate(100, 60, 10)
    assert run_rule("bbox_match", s, spec(bbox=BBox(x=100, y=60, z=10, tol=0.5))) == []
    out = run_rule("bbox_match", s, spec(bbox=BBox(x=100, y=60, z=15, tol=0.5)))
    assert len(out) == 1 and out[0].target == "z" and "10.00" in out[0].message and "5.00" in out[0].hint
    assert run_rule("bbox_match", s, spec()) == []   # skipped when empty


def test_hole_count():
    s = plate_holes([(-10, 0), (10, 0)], 5)
    assert run_rule("hole_count", s, spec(hole_count=2)) == []
    out = run_rule("hole_count", s, spec(hole_count=4))
    assert out and out[0].measured == 2 and out[0].required == 4
    assert run_rule("hole_count", s, spec()) == []


def test_hole_diameter():
    s = plate_holes([(-10, 0), (10, 0)], 5)
    assert run_rule("hole_diameter", s, spec(hole_diameters=[5.0, 5.05])) == []
    out = run_rule("hole_diameter", s, spec(hole_diameters=[5.0, 6.6]))
    assert out and "6.60" in out[0].message
    assert run_rule("hole_diameter", s, spec()) == []


def test_volume_range():
    s = plate(10, 10, 10)  # 1000
    assert run_rule("volume_range", s, spec(volume_range=(900, 1100))) == []
    assert run_rule("volume_range", s, spec(volume_range=(None, None))) == []
    assert run_rule("volume_range", s, spec(volume_range=(None, 900)))[0].required == 900
    assert run_rule("volume_range", s, spec(volume_range=(1100, None)))[0].required == 1100


# ---------------------------------------------------------------------- L3

def test_hole_edge_distance():
    ok = plate_holes([(30, 0)], 6)            # 20 from edge, need 9
    assert run_rule("hole_edge_distance", ok) == []
    bad = plate_holes([(50 - 4, 0)], 6)       # 4 from edge
    out = run_rule("hole_edge_distance", bad)
    assert len(out) == 1 and out[0].severity == "error"
    assert abs(out[0].measured - 4.0) < 1e-3 and abs(out[0].required - 9.0) < 1e-3
    assert "4.0mm" in out[0].message and "9.0mm" in out[0].message and "5.0" in out[0].hint


def test_internal_corner_radius():
    sharp = cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(20, 20).cutThruAll().val()
    blind = (cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(20, 20).cutBlind(-5)
             .edges("|Z").edges(cq.selectors.BoxSelector((-11, -11, -6), (11, 11, 6))).fillet(3).val())
    # vertical corners are R3 but the floor edges stay sharp
    assert any(i.severity == "error" and "尖角" in i.message for i in run_rule("internal_corner_radius", blind))
    out = run_rule("internal_corner_radius", sharp)
    assert any(i.severity == "error" for i in out)
    r3 = (cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(20, 20).cutThruAll()
          .edges("|Z").edges(cq.selectors.BoxSelector((-11, -11, -6), (11, 11, 6))).fillet(3).val())
    assert not [i for i in run_rule("internal_corner_radius", r3) if i.severity == "error"]
    r1 = (cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(20, 20).cutThruAll()
          .edges("|Z").edges(cq.selectors.BoxSelector((-11, -11, -6), (11, 11, 6))).fillet(1).val())
    w = run_rule("internal_corner_radius", r1)
    assert any(i.severity == "warning" and abs(i.measured - 1) < 1e-3 for i in w)
    tiny = (cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(20, 20).cutThruAll()
            .edges("|Z").edges(cq.selectors.BoxSelector((-11, -11, -6), (11, 11, 6))).fillet(0.3).val())
    assert any(i.severity == "error" and abs(i.measured - 0.3) < 1e-3 for i in run_rule("internal_corner_radius", tiny))


def test_internal_corner_radius_ignores_plain_box_and_holes():
    assert run_rule("internal_corner_radius", plate()) == []
    blind = cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().hole(6, 5).val()
    assert not [i for i in run_rule("internal_corner_radius", blind) if i.severity == "error"
                and i.target == "internal_edges"]


def test_min_wall_thickness():
    def slab(t):
        return cq.Workplane("XY").box(50, 50, t).val()
    assert run_rule("min_wall_thickness", slab(5)) == []
    w = run_rule("min_wall_thickness", slab(1.8))
    assert len(w) == 1 and w[0].severity == "warning" and abs(w[0].measured - 1.8) < 1e-3
    e = run_rule("min_wall_thickness", slab(1.0))
    assert len(e) == 1 and e[0].severity == "error" and "1.00" in e[0].message


def test_min_wall_ignores_gap_between_disjoint_faces():
    # pocket 1mm wide: opposite faces are air-separated (material is outside), not a wall
    s = cq.Workplane("XY").box(40, 40, 10).faces(">Z").workplane().rect(30, 1).cutBlind(-5).val()
    assert not [i for i in run_rule("min_wall_thickness", s) if abs(i.measured - 1.0) < 1e-3]


def test_hole_spacing():
    ok = plate_holes([(-10, 0), (10, 0)], 5)
    assert run_rule("hole_spacing", ok) == []
    bad = plate_holes([(-3.5, 0), (3.5, 0)], 5)   # gap 2 < 5
    out = run_rule("hole_spacing", bad)
    assert len(out) == 1 and abs(out[0].measured - 2.0) < 1e-3


# ------------------------------------------------------------- L-bracket

BR_SPEC = PartSpec(assertions=Assertions(hole_count=5, hole_diameters=[6.6] * 4 + [20], diameter_tol=0.1))


def test_bracket_bad():
    issues = run_checks(bracket(True), BR_SPEC, CFG)
    errs = rules(issues, sev="error")
    assert len(rules(errs, "hole_edge_distance")) == 4, [i.message for i in issues]
    assert len(rules(errs, "internal_corner_radius")) >= 1
    assert not rules(issues, "hole_count") and not rules(issues, "hole_diameter")


def test_bracket_good():
    issues = run_checks(bracket(False), BR_SPEC, CFG)
    assert not rules(issues, sev="error"), [i.message for i in issues]


def test_run_checks_tolerates_missing_cfg():
    assert not rules(run_checks(plate(), spec(), {}), sev="error")
    assert not rules(run_checks(cq.Workplane("XY").box(20, 20, 20), spec(), None), sev="error")


# ------------------------------------------------------------ hole_breakout

def llm_bad_bracket():
    """Geometry from an LLM script: the Ø20 hole is cut from the base's +Y face at base mid-height,
    producing a slot through the base and a notch at the foot of the wall."""
    base = cq.Workplane("XY").box(100, 60, 6, centered=(True, True, False))
    wall = (cq.Workplane("XY").workplane(offset=6).center(0, -30 + 2).rect(100, 4).extrude(40))
    body = base.union(wall)
    body = body.edges(cq.selectors.BoxSelector((-100, -26 - 0.1, 5.9), (100, -26 + 0.1, 6.1))).fillet(3)
    pts = [(sx * 36.8, sy * 16.8) for sx in (-1, 1) for sy in (-1, 1)]
    body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(6.6)
    body = body.faces(">Y").workplane(centerOption="CenterOfBoundBox").center(0, 0).hole(20.0)
    return body.val()


def good_bracket(wall_h=40):
    """Same bracket, Ø20 hole correctly centred in the wall (wall tall enough for the capped edge rule)."""
    base = cq.Workplane("XY").box(100, 60, 6, centered=(True, True, False))
    wall = cq.Workplane("XY").workplane(offset=6).center(0, -28).rect(100, 4).extrude(wall_h)
    body = base.union(wall).edges(cq.selectors.BoxSelector((-100, -26.1, 5.9), (100, -25.9, 6.1))).fillet(3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body = body.cut(cq.Workplane("XY").circle(3.3).extrude(10).translate((sx * 36.8, sy * 16.8, -2)))
    body = body.cut(cq.Workplane("XZ").center(0, 6 + wall_h / 2).circle(10).extrude(10).translate((0, -20, 0)))
    return body.val()


def test_hole_breakout_llm_bracket():
    issues = run_checks(llm_bad_bracket(), BR_SPEC, CFG, levels=("L1", "L2"))
    hb = rules(issues, "hole_breakout", "error")
    assert hb, [i.message for i in issues]
    assert "Ø20" in hb[0].message and "mm" in hb[0].hint


def test_hole_breakout_good_bracket():
    s = good_bracket()
    assert not rules(run_checks(s, BR_SPEC, CFG), "hole_breakout")
    assert not rules(run_checks(s, BR_SPEC, CFG), sev="error"), [i.message for i in run_checks(s, BR_SPEC, CFG)]


def test_hole_breakout_ignores_fillets_slots_and_holes():
    filleted = cq.Workplane("XY").box(30, 30, 10).edges("|Z").fillet(3).val()
    assert run_rule("hole_breakout", filleted) == []
    l = cq.Workplane("XY").box(40, 40, 6).union(cq.Workplane("XY").box(40, 4, 30).translate((0, -18, 15)))
    l = l.edges(cq.selectors.BoxSelector((-30, -16.1, 2.9), (30, -15.9, 3.1))).fillet(3).val()
    assert run_rule("hole_breakout", l) == []
    slot = cq.Workplane("XY").box(50, 30, 6).faces(">Z").workplane().slot2D(20, 6).cutThruAll().val()
    assert run_rule("hole_breakout", slot) == []
    assert run_rule("hole_breakout", plate_holes([(10, 0)], 8)) == []


def test_hole_breakout_edge_notch():
    notch = cq.Workplane("XY").box(50, 30, 6).cut(cq.Workplane("XY").circle(5).extrude(10).translate((25 - 2, 0, -2))).val()
    out = run_rule("hole_breakout", notch)
    assert len(out) == 1 and out[0].severity == "error" and "Ø10" in out[0].message
