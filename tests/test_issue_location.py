"""Issue.location is in the script frame, which is also the part.glb frame (before its Y-up node rotation)."""
import struct
import json

import cadquery as cq
import numpy as np
import yaml

from core.checks import run_checks
from core.models import PartSpec
from web.server.meshing import write_glb

CFG = yaml.safe_load(open("config.yaml"))


def issues(wp, rule):
    return [i for i in run_checks(wp.val(), PartSpec(), CFG, levels=("L3",)) if i.rule == rule]


def l_bracket(fillet):
    b = cq.Workplane("XY").box(100, 60, 6, centered=(True, True, False))
    w = cq.Workplane("XY").workplane(offset=6).center(0, -28.5).rect(100, 3).extrude(40)
    b = b.union(w)
    return b.edges(cq.selectors.BoxSelector((-60, -28, 5), (60, -26, 7))).fillet(3) if fillet else b


def glb_vertices(path):
    data = path.read_bytes()
    jl = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + jl])
    off = 20 + jl + 8
    n = js["accessors"][0]["count"]
    return np.frombuffer(data, dtype="<f4", count=n * 3, offset=off).reshape(-1, 3)


def test_sharp_corner_location_matches_glb(tmp_path):
    wp = l_bracket(False)
    (i,) = issues(wp, "internal_corner_radius")
    assert i.location == [0.0, -27.0, 6.0]
    v = glb_vertices(write_glb(wp.val(), tmp_path / "p.glb"))
    assert np.any(np.linalg.norm(v[:, 1:] - np.array([-27.0, 6.0]), axis=1) < 1e-3)  # corner line is on the mesh


def test_no_issue_no_location():
    assert not [i for i in issues(l_bracket(True), "internal_corner_radius") if i.severity == "error"]


def test_hole_edge_location():
    p = cq.Workplane("XY").box(40, 40, 6, centered=(True, True, False)).faces(">Z").workplane().center(-17, 0).hole(6)
    (i,) = issues(p, "hole_edge_distance")
    assert abs(i.location[0] + 17) < 1e-3 and abs(i.location[1]) < 1e-3 and abs(i.location[2] - 3) < 1e-3
    ok = cq.Workplane("XY").box(60, 60, 6, centered=(True, True, False)).faces(">Z").workplane().hole(6)
    assert not issues(ok, "hole_edge_distance")


def test_thin_wall_location():
    w = cq.Workplane("XY").box(30, 1.0, 20, centered=(True, True, False))
    (i,) = issues(w, "min_wall_thickness")
    assert i.location is not None and abs(i.location[1]) <= 0.5 + 1e-6
