"""Private feature helpers for the drawing module: exact bbox, counterbore pairing, slot detection."""
from __future__ import annotations

import math

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder


def exact_bbox(shape: cq.Shape):
    """(xmin, ymin, zmin, xmax, ymax, zmax) from geometry only (no shape tolerance, no mesh)."""
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        b = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape.wrapped, b, False, False)
        v = [round(x, 6) for x in b.Get()]
        if all(math.isfinite(x) for x in v) and v[3] > v[0] - 1e-9:
            return tuple(v)
    except Exception:
        pass
    bb = shape.BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)


def axis_view(d):
    """View in which an axis along d is seen end-on, or None if not axis-aligned."""
    c = (d.x, d.y, d.z)
    ax = max(range(3), key=lambda i: abs(c[i]))
    if abs(c[ax]) < 0.999:
        return None
    return ("right", "front", "top")[ax]


def _canon(v: cq.Vector):
    c = (v.x, v.y, v.z)
    i = max(range(3), key=lambda k: abs(c[k]))
    return v if c[i] >= 0 else v * -1


def _hole_item(h):
    return dict(kind="hole", d=h.diameter, D=None, depth_c=0.0, through=bool(h.through),
                depth=h.depth, center=h.center, direction=h.direction, a=h.center, b=h.center,
                r=h.radius, length=None)


def pair_counterbores(holes):
    """Merge coaxial touching holes of different diameter (counterbore / stepped) into one item."""
    used, items = set(), []
    for i, big in enumerate(holes):
        if i in used:
            continue
        for j, small in enumerate(holes):
            if j == i or j in used or small.diameter >= big.diameter - 1e-4:
                continue
            d = small.direction
            if abs(abs(d.dot(big.direction)) - 1) > 1e-6:
                continue
            off = big.origin - small.origin
            if (off - d * off.dot(d)).Length > 1e-3:
                continue
            s0, s1 = small.origin.dot(d), small.origin.dot(d) + small.depth
            b0 = big.origin.dot(d)
            b1 = b0 + big.depth
            if big.direction.dot(d) < 0:
                b0, b1 = big.origin.dot(d) - big.depth, big.origin.dot(d)
            if abs(b0 - s1) > 1e-3 and abs(b1 - s0) > 1e-3:
                continue
            used.update((i, j))
            c = small.center
            items.append(dict(kind="cbore", d=small.diameter, D=big.diameter, depth_c=big.depth,
                              through=bool(small.through), depth=small.depth + big.depth,
                              center=c, direction=d, a=c, b=c, r=big.radius, length=None))
            break
    for k, h in enumerate(holes):
        if k not in used:
            items.append(_hole_item(h))
    return items


def find_slots(shape: cq.Shape):
    """Obround slots: two concave half-cylinders (u-span ~ pi) of equal radius facing each other."""
    from core.checks.features import point_in_solid
    cyls = []
    for f in shape.Faces():
        try:
            s = BRepAdaptor_Surface(f.wrapped)
            if s.GetType() != GeomAbs_Cylinder:
                continue
            span = s.LastUParameter() - s.FirstUParameter()
            if abs(span - math.pi) > 0.02:
                continue
            cy = s.Cylinder()
            ax, loc = cy.Axis().Direction(), cy.Axis().Location()
            d0 = cq.Vector(ax.X(), ax.Y(), ax.Z())
            lc = cq.Vector(loc.X(), loc.Y(), loc.Z())
            d = _canon(d0)
            p1 = lc + d0 * s.FirstVParameter()
            p2 = lc + d0 * s.LastVParameter()
            t1, t2 = sorted((p1.dot(d), p2.dot(d)))
            foot = lc - d * lc.dot(d)
            cyls.append(dict(r=cy.Radius(), d=d, foot=foot, t1=t1, t2=t2, face=f))
        except Exception:
            continue
    slots: list = []
    used: set = set()
    for i, a in enumerate(cyls):
        if i in used:
            continue
        for j in range(i + 1, len(cyls)):
            b = cyls[j]
            if j in used or abs(a["r"] - b["r"]) > 1e-4 or abs(a["d"].dot(b["d"])) < 1 - 1e-9:
                continue
            if abs(a["t1"] - b["t1"]) > 1e-3 or abs(a["t2"] - b["t2"]) > 1e-3:
                continue
            sep = b["foot"] - a["foot"]
            c2c = sep.Length
            if c2c < 1e-3:
                continue
            # concave halves facing each other: each face centre lies on the far side of its own axis
            ca = a["face"].Center() - a["foot"]
            cb = b["face"].Center() - b["foot"]
            if ca.dot(sep) >= 0 or cb.dot(sep) <= 0:
                continue
            d = a["d"]
            tm = (a["t1"] + a["t2"]) / 2
            pa, pb = a["foot"] + d * tm, b["foot"] + d * tm
            mid = (pa + pb) * 0.5
            if point_in_solid(shape, mid) or point_in_solid(shape, pa) or point_in_solid(shape, pb):
                continue
            eps = 0.01
            through = (not point_in_solid(shape, mid + d * (a["t1"] - tm - eps))
                       and not point_in_solid(shape, mid + d * (a["t2"] - tm + eps)))
            used.update((i, j))
            slots.append(dict(kind="slot", d=2 * a["r"], D=None, depth_c=0.0, through=through,
                              depth=a["t2"] - a["t1"], center=mid, direction=d, a=pa, b=pb,
                              r=a["r"], length=c2c + 2 * a["r"]))
            break
    return slots


def front_section(shape: cq.Shape, cy: float, bb):
    """Section by the plane y=cy keeping y>=cy, seen from -Y.

    Returns (visible polylines [(x,z)], hatch loops [[(x,z)]]) or None.
    """
    from .hlr import _edge_polyline, _hlr_view
    xmin, ymin, zmin, xmax, ymax, zmax = bb
    if cy - ymin < 1e-3 or ymax - cy < 1e-3:
        return None
    box = cq.Solid.makeBox(xmax - xmin + 2, ymax - cy + 1, zmax - zmin + 2, pnt=cq.Vector(xmin - 1, cy, zmin - 1))
    half = shape.intersect(box)
    defl = max(cq.Shape.BoundingBox(half).DiagonalLength, 1.0) * 0.002
    vis, _hid = _hlr_view(half, "front", defl)
    loops = []
    for f in half.Faces():
        if f.geomType() != "PLANE" or abs(f.Center().y - cy) > 1e-4 or f.normalAt().y > -0.999:
            continue
        for w in [f.outerWire()] + list(f.innerWires()):
            segs = []
            for e in w.Edges():
                try:
                    segs.append([(p[0], p[2]) for p in _edge_polyline(e.wrapped, defl)])
                except Exception:
                    pass
            if not segs:
                continue
            chain = list(segs.pop(0))
            while segs:
                end = chain[-1]
                for k, sg in enumerate(segs):
                    if math.dist(sg[0], end) < 1e-4:
                        chain += sg[1:]
                        segs.pop(k)
                        break
                    if math.dist(sg[-1], end) < 1e-4:
                        chain += sg[::-1][1:]
                        segs.pop(k)
                        break
                else:
                    chain += segs.pop(0)
            if math.dist(chain[0], chain[-1]) < 1e-4:
                chain.pop()
            if len(chain) >= 3:
                loops.append(chain)
    if not loops:
        return None
    return vis, loops
