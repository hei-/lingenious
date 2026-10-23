import cadquery as cq
import ezdxf

from core.drawing import draw


def l_bracket():
    base = cq.Workplane("XY").box(100, 60, 6, centered=False)
    wall = cq.Workplane("XY").box(100, 3, 40, centered=False).translate((0, 0, 6))
    s = base.union(wall)
    s = s.cut(cq.Workplane("XY").pushPoints([(12, 12), (88, 12), (12, 48), (88, 48)])
              .circle(3.3).extrude(6))
    s = s.cut(cq.Workplane("XZ").center(50, 26).circle(10).extrude(-3))
    return s.val()


def _texts(path):
    doc = ezdxf.readfile(path)
    return doc, [e.dxf.text for e in doc.modelspace().query("TEXT")]


def test_l_bracket(tmp_path):
    r = draw(l_bracket(), tmp_path, name="L-bracket", material="Q235")
    assert r["holes"] == 5
    assert r["dxf"].stat().st_size > 5000 and r["pdf"].stat().st_size > 3000
    assert r["hlr"] is True
    doc, texts = _texts(r["dxf"])
    msp = doc.modelspace()
    layers = {e.dxf.layer for e in msp}
    assert {"VISIBLE", "HIDDEN", "DIM", "TEXT"} <= layers
    assert len(msp.query('*[layer=="HIDDEN"]')) > 0
    assert "Ø6.6" in texts and "Ø20" in texts   # hole table rows
    assert "4" in texts and "100" in texts and "L-bracket" in texts
    assert any("THIRD ANGLE" in t for t in texts)


def test_box(tmp_path):
    r = draw(cq.Workplane("XY").box(50, 30, 20).val(), tmp_path)
    assert r["holes"] == 0
    assert r["dxf"].exists() and r["pdf"].stat().st_size > 1000
    doc, texts = _texts(r["dxf"])
    assert {"50", "30", "20"} <= set(texts)
    assert "HOLE TABLE" not in texts


# ---------------------------------------------------------------- improved annotation
from pathlib import Path

from core.drawing.layout import boxes_overlap, text_bbox

REFS = Path(__file__).resolve().parent.parent / "eval" / "refs"


def ref(name):
    ns: dict = {}
    exec((REFS / f"{name}.py").read_text(), ns)
    r = ns["result"]
    return r.val() if hasattr(r, "val") else r


def _boxes(path):
    doc = ezdxf.readfile(path)
    out = []
    for e in doc.modelspace().query("TEXT"):
        al, p = e.get_placement()[0], e.get_placement()[1]
        a = {"LEFT": "L", "CENTER": "C", "RIGHT": "R"}[al.name]
        out.append((e.dxf.text, text_bbox(p.x, p.y, e.dxf.text, e.dxf.height, e.dxf.rotation, a)))
    return out


def _assert_no_overlap(path):
    bx = _boxes(path)
    bad = [(a[0], b[0]) for i, a in enumerate(bx) for b in bx[i + 1:] if boxes_overlap(a[1], b[1])]
    assert not bad, bad


def test_no_text_overlap_bracket(tmp_path):
    r = draw(l_bracket(), tmp_path)
    _assert_no_overlap(r["dxf"])


def test_no_text_overlap_flange(tmp_path):
    flange = (cq.Workplane("XY").circle(50).extrude(10).faces(">Z").workplane()
              .hole(30).faces(">Z").workplane().polarArray(33, 0, 360, 6).hole(9))
    r = draw(flange.val(), tmp_path)
    _assert_no_overlap(r["dxf"])
    _, texts = _texts(r["dxf"])
    assert texts.count("100") == 3 and "100.03" not in "".join(texts)   # exact extents


def test_exact_dims_circle(tmp_path):
    s = cq.Workplane("XY").circle(50).extrude(10).val()
    _, texts = _texts(draw(s, tmp_path)["dxf"])
    assert "100" in texts and "10" in texts
    from core.drawing.feat import exact_bbox
    bb = exact_bbox(s)
    assert abs(bb[3] - bb[0] - 100) < 1e-4


def test_counterbore_label(tmp_path):
    r = draw(ref("h3"), tmp_path)
    assert r["counterbores"] == 8
    _, texts = _texts(r["dxf"])
    assert any("⌴" in t and "Ø15" in t and "↧6" in t and "8x" in t for t in texts)
    assert r["section"] is True
    assert len(ezdxf.readfile(r["dxf"]).modelspace().query('*[layer=="HATCH"]')) > 10
    _assert_no_overlap(r["dxf"])


def test_slot_label(tmp_path):
    r = draw(ref("e5"), tmp_path)
    assert r["slots"] == 1
    _, texts = _texts(r["dxf"])
    assert any("30×10" in t for t in texts)
    _assert_no_overlap(r["dxf"])


def test_blind_holes_section(tmp_path):
    r = draw(ref("m8"), tmp_path)
    assert r["section"] is True
    _, texts = _texts(r["dxf"])
    assert "SECTION A-A" in texts and "A" in texts


def test_pocket_plate_ok(tmp_path):
    r = draw(ref("m7"), tmp_path)
    assert r["holes"] == 4
    _assert_no_overlap(r["dxf"])


def test_oblique_hole_note(tmp_path):
    body = cq.Workplane("XY").box(40, 40, 20)
    cyl = (cq.Workplane("XY").circle(3).extrude(60).translate((0, 0, -30))
           .rotate((0, 0, 0), (1, 0, 0), 40))
    r = draw(body.cut(cyl).val(), tmp_path)
    assert r["oblique_groups"] == 1
    _, texts = _texts(r["dxf"])
    assert any(t.startswith("NOTE: AXIS OF") for t in texts)
