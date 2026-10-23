"""Shared B-Rep feature queries (holes, edge convexity, edge distance).

All lengths in mm. Used by both L2 and L3 rules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN, TopAbs_ON
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.gp import gp_Pnt

V = cq.Vector


@dataclass
class Hole:
    id: str
    origin: cq.Vector          # point on the axis at the lowest axial coordinate
    direction: cq.Vector       # unit axis, canonical sign
    diameter: float
    depth: float
    through: bool
    faces: list = field(default_factory=list, repr=False)

    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    def point_at(self, s: float) -> cq.Vector:
        """Axis point at distance s from origin along direction."""
        return self.origin + self.direction * s

    @property
    def center(self) -> cq.Vector:
        return self.point_at(self.depth / 2.0)


# ---------------------------------------------------------------- primitives

def dist(a, b) -> float:
    """Minimum distance between two cq shapes."""
    d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    d.Perform()
    return d.Value() if d.IsDone() else float("inf")


def point_in_solid(shape: cq.Shape, p: cq.Vector, tol: float = 1e-6) -> bool:
    c = BRepClass3d_SolidClassifier(shape.wrapped, gp_Pnt(p.x, p.y, p.z), tol)
    return c.State() == TopAbs_IN


def point_in_face(face: cq.Face, p: cq.Vector, tol: float = 1e-6) -> bool:
    c = BRepClass_FaceClassifier(face.wrapped, gp_Pnt(p.x, p.y, p.z), tol)
    return c.State() in (TopAbs_IN, TopAbs_ON)


def loc(p) -> list[float]:
    """Point -> [x, y, z] rounded, for Issue.location."""
    return [round(float(p.x), 3), round(float(p.y), 3), round(float(p.z), 3)]


def fmt_pt(p: cq.Vector) -> str:
    return f"({p.x:.1f}, {p.y:.1f}, {p.z:.1f})"


def _canon(d: cq.Vector):
    """Return (unit direction with canonical sign, sign applied)."""
    d = d.normalized()
    for c in (d.x, d.y, d.z):
        if abs(c) > 1e-9:
            if c < 0:
                return d * -1, -1
            return d, 1
    return d, 1


def cylinder_info(face: cq.Face):
    """For a cylindrical face return (loc, dir, radius, u_cover, v1, v2, concave) else None."""
    s = BRepAdaptor_Surface(face.wrapped)
    if s.GetType() != GeomAbs_Cylinder:
        return None
    cyl = s.Cylinder()
    ax = cyl.Axis()
    loc = V(ax.Location().X(), ax.Location().Y(), ax.Location().Z())
    dr = V(ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z())
    u1, u2, v1, v2 = s.FirstUParameter(), s.LastUParameter(), s.FirstVParameter(), s.LastVParameter()
    pm = s.Value((u1 + u2) / 2, (v1 + v2) / 2)
    p = V(pm.X(), pm.Y(), pm.Z())
    radial = p - (loc + dr * ((p - loc).dot(dr)))
    n = face.normalAt(p)
    concave = n.dot(radial) < 0
    return loc, dr, cyl.Radius(), u2 - u1, v1, v2, concave


def is_hole_face(face: cq.Face) -> bool:
    info = cylinder_info(face)
    return bool(info and info[6] and info[3] > math.pi + 1e-3)


# ------------------------------------------------------------------- holes

_cache: dict = {}


def find_holes(shape: cq.Shape) -> list[Hole]:
    key = id(shape.wrapped)
    hit = _cache.get("k")
    if hit and hit[0] == key and hit[1] is shape.wrapped:
        return hit[2]
    holes = _find_holes(shape)
    _cache["k"] = (key, shape.wrapped, holes)
    return holes


def _find_holes(shape: cq.Shape) -> list[Hole]:
    items = []  # dict(dir, r, loc, t1, t2, face)
    for f in shape.Faces():
        info = cylinder_info(f)
        if not info:
            continue
        loc, dr, r, cover, v1, v2, concave = info
        if not concave or cover <= math.pi + 1e-3:
            continue
        d, sign = _canon(dr)
        base = loc.dot(d)
        a, b = (base + v1 * sign, base + v2 * sign)
        t1, t2 = min(a, b), max(a, b)
        # axis point at t=0 (global): loc - (loc.d) d
        foot = loc - d * base
        items.append(dict(d=d, r=r, foot=foot, t1=t1, t2=t2, face=f))

    # merge coaxial, same-radius, axially touching/overlapping faces
    groups: list[list[dict]] = []
    for it in items:
        placed = False
        for g in groups:
            h = g[0]
            if (abs(h["r"] - it["r"]) < 1e-4 and abs(h["d"].dot(it["d"])) > 1 - 1e-9
                    and (h["foot"] - it["foot"]).Length < 1e-4):
                if any(it["t1"] <= o["t2"] + 1e-4 and it["t2"] >= o["t1"] - 1e-4 for o in g):
                    g.append(it)
                    placed = True
                    break
        if not placed:
            groups.append([it])
    # transitive merge not needed for typical splits (chains handled by append order),
    # but do a second pass for safety
    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i][0], groups[j][0]
                if (abs(a["r"] - b["r"]) < 1e-4 and abs(a["d"].dot(b["d"])) > 1 - 1e-9
                        and (a["foot"] - b["foot"]).Length < 1e-4
                        and min(x["t1"] for x in groups[j]) <= max(x["t2"] for x in groups[i]) + 1e-4
                        and max(x["t2"] for x in groups[j]) >= min(x["t1"] for x in groups[i]) - 1e-4):
                    groups[i] += groups[j]
                    del groups[j]
                    merged = True
                    break
            if merged:
                break

    holes = []
    for g in groups:
        d, foot, r = g[0]["d"], g[0]["foot"], g[0]["r"]
        t1, t2 = min(x["t1"] for x in g), max(x["t2"] for x in g)
        eps = 0.01
        through = (not point_in_solid(shape, foot + d * (t1 - eps))
                   and not point_in_solid(shape, foot + d * (t2 + eps)))
        holes.append(Hole(id="", origin=foot + d * t1, direction=d, diameter=2 * r,
                          depth=t2 - t1, through=through, faces=[x["face"] for x in g]))
    holes.sort(key=lambda h: (round(h.direction.x, 3), round(h.direction.y, 3), round(h.direction.z, 3),
                              round(h.center.x, 2), round(h.center.y, 2), round(h.center.z, 2),
                              h.diameter))
    for i, h in enumerate(holes, 1):
        h.id = f"hole{i}"
    return holes


# ------------------------------------------------------- edge convexity

def _edge_faces(shape: cq.Shape):
    """Yield (edge, [faces]) for every edge of the shape."""
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, TopAbs_EDGE, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        e = cq.Edge(m.FindKey(i))
        fs = []
        for f in m.FindFromIndex(i):
            if not any(f.IsSame(x.wrapped) for x in fs):
                fs.append(cq.Face(f))
        out.append((e, fs))
    return out


def edge_is_concave(edge: cq.Edge, f1: cq.Face, f2: cq.Face) -> Optional[bool]:
    """True if the edge between f1 and f2 is a concave (internal) edge, False if convex,
    None if the faces join tangentially (smooth)."""
    try:
        m = edge.positionAt(0.5)
        t = edge.tangentAt(0.5)
        n1, n2 = f1.normalAt(m), f2.normalAt(m)
    except Exception:
        return None
    if n1.dot(n2) > math.cos(math.radians(1.0)):
        return None
    side = n1.cross(t)
    if side.Length < 1e-9:
        return None
    side = side.normalized()
    # outward in-face direction of f1: the sign for which a small step leaves f1
    u = side
    if point_in_face(f1, m + side * 0.05, 1e-7):
        u = side * -1
        if point_in_face(f1, m + u * 0.05, 1e-7):
            return None
    # f1 lies on the -u side; concave iff f1 sits on the outer side of f2's plane
    return (u * -1).dot(n2) > 1e-9


def _tangent_concave(f2: cq.Face) -> bool:
    info = cylinder_info(f2)
    return bool(info and info[6])


def free_outer_edges(face: cq.Face, solid: cq.Shape, adj: dict):
    """Edges of the face's outer wire that are real boundary edges (convex, or a smooth
    round-over), excluding concave junctions where material continues (walls, fillets)."""
    res = []
    for e in face.outerWire().Edges():
        others = [x for x in _lookup(adj, e) if not x.wrapped.IsSame(face.wrapped)]
        if not others:
            res.append(e)
            continue
        o = others[0]
        c = edge_is_concave(e, face, o)
        if c is None:  # tangent
            if _tangent_concave(o):
                continue
            res.append(e)
        elif not c:
            res.append(e)
    return res


def _lookup(adj: dict, e: cq.Edge) -> list:
    for edge, fs in adj.get(e.hashCode(), []):
        if edge.wrapped.IsSame(e.wrapped):
            return fs
    return []


def adjacency(shape: cq.Shape) -> dict:
    adj: dict = {}
    for e, fs in _edge_faces(shape):
        adj.setdefault(e.hashCode(), []).append((e, fs))
    return adj


def hole_edge_distance(shape: cq.Shape, hole: Hole):
    """Distance from the hole axis to the nearest free outer edge on the face(s) the hole opens on.

    Returns (distance, face_point) or None if the opening face cannot be identified.
    """
    adj = adjacency(shape)
    d, r = hole.direction, hole.radius
    best = None
    for end in (0.0, hole.depth):
        E = hole.point_at(end)
        for f in shape.Faces():
            if f.geomType() != "PLANE":
                continue
            n = f.normalAt()
            if abs(n.dot(d)) < 0.999:
                continue
            if abs((f.Center() - E).dot(d)) > 1e-4:
                continue
            # the hole's opening must be an inner wire of this face
            opening = False
            for w in f.innerWires():
                if abs(dist(cq.Vertex.makeVertex(E.x, E.y, E.z), w) - r) < 1e-3:
                    opening = True
                    break
            if not opening:
                continue
            for e in free_outer_edges(f, shape, adj):
                dd = dist(cq.Vertex.makeVertex(E.x, E.y, E.z), e)
                if best is None or dd < best[0]:
                    best = (dd, E)
    return best


# ---------------------------------------------------------- breakout arcs

def find_breakouts(shape: cq.Shape, min_cover=math.radians(120), max_cover=math.radians(355)) -> list[dict]:
    """Concave cylindrical partial arcs that end on a non-tangent edge, i.e. a hole/slot cut
    through an outer edge or face (notch). Round slot ends and fillets end tangentially and are
    not reported. Coaxial same-radius arcs are merged into one entry:
    dict(diameter, center, direction, edge_dist, faces); edge_dist is the signed distance from the
    axis to the plane it breaks (positive = axis inside the material, negative = outside)."""
    ef = _edge_faces(shape)
    arcs = []
    for f in shape.Faces():
        info = cylinder_info(f)
        if not info:
            continue
        loc, dr, r, cover, v1, v2, concave = info
        if not concave or cover < min_cover or cover > max_cover:
            continue
        d, sign = _canon(dr)
        base = loc.dot(d)
        t1, t2 = sorted((base + v1 * sign, base + v2 * sign))
        foot = loc - d * base
        planes, broken = [], False
        for e, fs in ef:
            if not any(x.wrapped.IsSame(f.wrapped) for x in fs):
                continue
            if e.geomType() != "LINE":
                continue
            if abs(e.tangentAt(0.5).normalized().dot(d)) < 0.99:
                continue
            for o in fs:
                if o.wrapped.IsSame(f.wrapped):
                    continue
                if (edge_is_concave(e, o, f) if o.geomType() == "PLANE" else edge_is_concave(e, f, o)) is not None:
                    broken = True
                    if o.geomType() == "PLANE":
                        planes.append(o)
        if not broken:
            continue
        axis_pt = foot + d * ((t1 + t2) / 2)
        ed = None
        for o in planes:
            dd = -((axis_pt - o.Center()).dot(o.normalAt()))
            ed = dd if ed is None else min(ed, dd)
        arcs.append(dict(r=r, d=d, foot=foot, t1=t1, t2=t2, ed=ed, face=f))
    groups: list[list[dict]] = []
    for a in arcs:
        for g in groups:
            h = g[0]
            if (abs(h["r"] - a["r"]) < 1e-4 and abs(h["d"].dot(a["d"])) > 1 - 1e-9
                    and (h["foot"] - a["foot"]).Length < 1e-4):
                g.append(a)
                break
        else:
            groups.append([a])
    out = []
    for g in groups:
        h = g[0]
        t1, t2 = min(x["t1"] for x in g), max(x["t2"] for x in g)
        eds = [x["ed"] for x in g if x["ed"] is not None]
        out.append(dict(diameter=2 * h["r"], center=h["foot"] + h["d"] * ((t1 + t2) / 2),
                        direction=h["d"], edge_dist=min(eds) if eds else None,
                        faces=[x["face"] for x in g]))
    out.sort(key=lambda o: (round(o["center"].x, 2), round(o["center"].y, 2), round(o["center"].z, 2)))
    return out
