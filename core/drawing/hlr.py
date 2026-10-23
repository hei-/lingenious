"""Hidden-line removal: project a solid into front/top/right 2D polylines.

Primary path: OCCT HLRBRep_Algo (exact HLR, sharp + silhouette edges, visible and hidden).
Fallback (if HLR raises): all edges projected without occlusion and reported as visible.

2D coordinates returned are world coordinates of the two axes shown by each view:
  front (looking +Y): (X, Z)   top (looking -Z): (X, Y)   right (looking -X): (Y, Z)
"""
from __future__ import annotations

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

# view -> (normal toward viewer N, screen-x direction X); screen-y = N x X
VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0)),
    "top": ((0, 0, 1), (1, 0, 0)),
    "right": ((1, 0, 0), (0, 1, 0)),
}
_AXES = {"front": (0, 2), "top": (0, 1), "right": (1, 2)}


def _edge_polyline(edge_wrapped, defl: float):
    ad = BRepAdaptor_Curve(edge_wrapped)
    td = GCPnts_TangentialDeflection(ad, 0.1, defl)
    n = td.NbPoints()
    return [(td.Value(i).X(), td.Value(i).Y(), td.Value(i).Z()) for i in range(1, n + 1)]


def _polys(compound, defl: float):
    out: list = []
    if compound is None or compound.IsNull():
        return out
    for e in cq.Compound(compound).Edges():
        try:
            pts = _edge_polyline(e.wrapped, defl)
        except Exception:
            continue
        if len(pts) >= 2:
            out.append([(p[0], p[1]) for p in pts])
    return out


def _hlr_view(shape: cq.Shape, view: str, defl: float):
    n, x = VIEWS[view]
    proj = HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*n), gp_Dir(*x)))
    algo = HLRBRep_Algo()
    algo.Add(shape.wrapped)
    algo.Projector(proj)
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    vis, hid = [], []
    # sharp edges + silhouettes; smooth (tangent) seam edges are deliberately omitted
    for getter in (h.VCompound, h.OutLineVCompound):
        try:
            vis += _polys(getter(), defl)
        except Exception:
            pass
    for getter in (h.HCompound, h.OutLineHCompound):
        try:
            hid += _polys(getter(), defl)
        except Exception:
            pass
    return vis, hid


def _fallback_view(shape: cq.Shape, view: str, defl: float):
    i, j = _AXES[view]
    vis = []
    for e in shape.Edges():
        try:
            pts = _edge_polyline(e.wrapped, defl)
        except Exception:
            continue
        vis.append([(p[i], p[j]) for p in pts])
    return vis, []


def project_views(shape: cq.Shape) -> tuple[dict, bool]:
    """Return ({view: {"visible": [...], "hidden": [...]}}, used_hlr)."""
    bb = shape.BoundingBox()
    defl = max(bb.DiagonalLength, 1.0) * 0.002
    res, used_hlr = {}, True
    for v in VIEWS:
        try:
            vis, hid = _hlr_view(shape, v, defl)
            if not vis and not hid:
                raise RuntimeError("empty HLR result")
        except Exception:
            vis, hid = _fallback_view(shape, v, defl)
            used_hlr = False
        res[v] = {"visible": vis, "hidden": hid}
    return res, used_hlr
