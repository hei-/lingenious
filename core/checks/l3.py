"""L3: DFM rules (approximate, B-Rep based)."""
from __future__ import annotations

import math

import cadquery as cq

from core.models import Issue
from .base import rule
from .features import (adjacency, cylinder_info, edge_is_concave, find_holes,
                       fmt_pt, hole_edge_distance, loc, is_hole_face, point_in_face, point_in_solid,
                       _edge_faces, _lookup, _tangent_concave)

V = cq.Vector


@rule("hole_edge_distance", "L3")
def hole_edge_distance_rule(shape, spec, c):
    k = c["hole_edge_factor"]
    out = []
    for h in find_holes(shape):
        res = hole_edge_distance(shape, h)
        if res is None:
            continue
        d, _ = res
        need = min(k * h.diameter, h.diameter / 2 + c.get("hole_edge_wall_cap", 6.0))  # large holes: cap wall-to-edge
        if d + 1e-6 < need:
            out.append(Issue(
                rule="hole_edge_distance", level="L3", target=h.id, location=loc(h.center), measured=round(d, 3), required=round(need, 3),
                message=f"孔 {h.id}(Ø{h.diameter:.1f},轴线 {fmt_pt(h.center)})中心距板边 {d:.1f}mm,"
                        f"要求不小于 {need:.1f}mm(min({k:g}×孔径, 半径+孔壁到边缘上限))",
                hint=f"将孔位向内移动至少 {need - d:.1f}mm,或减小孔径,或加宽该处板材"))
    return out


@rule("internal_corner_radius", "L3")
def internal_corner_radius(shape, spec, c):
    rmin, rrec = c["min_internal_radius"], c["recommended_internal_radius"]
    out = []
    # sharp concave edges
    sharp = []
    for e, fs in _edge_faces(shape):
        if len(fs) != 2:
            continue
        f1, f2 = fs
        if is_hole_face(f1) or is_hole_face(f2):
            continue
        try:
            if edge_is_concave(e, f1, f2):
                sharp.append(e)
        except Exception:
            continue
    if sharp:
        first = max(sharp, key=lambda e: e.Length())
        total = sum(e.Length() for e in sharp)
        out.append(Issue(
            rule="internal_corner_radius", level="L3", severity="error", target="internal_edges",
            measured=0.0, required=rrec, location=loc(first.positionAt(0.5)),
            message=f"存在 {len(sharp)} 条无圆角的内凹尖角(共长 {total:.1f}mm,最长一条位于 {fmt_pt(first.positionAt(0.5))}),"
                    f"圆角半径 0mm,要求不小于 {rmin:g}mm(建议 ≥{rrec:g}mm)",
            hint=f"对这些内凹边添加圆角 fillet,半径取 {rrec:g}mm(最小 {rmin:g}mm);"
                 f"在 CadQuery 中先选中内凹边再 fillet,或在建模时对草图拐角加圆角"))
    # filleted concave edges
    seen = {}
    for f in shape.Faces():
        info = cylinder_info(f)
        if not info or not info[6] or info[3] > math.pi + 1e-3:
            continue
        r = info[2]
        seen.setdefault(round(r, 3), []).append(f)
    for r, fs in sorted(seen.items()):
        if r + 1e-6 < rmin:
            out.append(Issue(
                rule="internal_corner_radius", level="L3", severity="error", target=f"R{r:g}", location=loc(fs[0].Center()),
                measured=r, required=rmin,
                message=f"{len(fs)} 处内圆角半径 R{r:g}mm,小于最小值 {rmin:g}mm(刀具无法加工)",
                hint=f"将内圆角半径增大到至少 {rmin:g}mm,建议 {rrec:g}mm"))
        elif r + 1e-6 < rrec:
            out.append(Issue(
                rule="internal_corner_radius", level="L3", severity="warning", target=f"R{r:g}", location=loc(fs[0].Center()),
                measured=r, required=rrec,
                message=f"{len(fs)} 处内圆角半径 R{r:g}mm,小于建议值 {rrec:g}mm",
                hint=f"建议将内圆角半径增大到 {rrec:g}mm 以便使用较大刀具、提高加工效率"))
    return out


def _grid(face: cq.Face, n: int = 7):
    bb = face.BoundingBox()
    pts = []
    for i in range(n):
        for j in range(n):
            for k in range(n):
                f = lambda a, b, t: a + (b - a) * (t + 0.5) / n
                pts.append(V(f(bb.xmin, bb.xmax, i), f(bb.ymin, bb.ymax, j), f(bb.zmin, bb.zmax, k)))
    return pts


@rule("min_wall_thickness", "L3")
def min_wall_thickness(shape, spec, c):
    emin, ewarn = c["min_wall_error"], c["min_wall_warn"]
    planar = []
    for f in shape.Faces():
        if f.geomType() == "PLANE":
            planar.append((f, f.normalAt(), f.Center()))
    found = []
    for i in range(len(planar)):
        fa, na, pa = planar[i]
        for j in range(i + 1, len(planar)):
            fb, nb, pb = planar[j]
            if na.dot(nb) > -0.995:
                continue
            t = (pb - pa).dot(na)          # B behind A (inside material side) when t < 0
            th = -t
            if th < 1e-4 or th >= ewarn - 1e-9:
                continue
            for (src, nsrc, psrc, dst, ndst, pdst) in ((fa, na, pa, fb, nb, pb), (fb, nb, pb, fa, na, pa)):
                hit = None
                for p in _grid(src):
                    p = p - nsrc * (p - psrc).dot(nsrc)           # onto src plane
                    if not point_in_face(src, p):
                        continue
                    q = p - nsrc * ((p - pdst).dot(nsrc))         # onto dst plane
                    if point_in_face(dst, q) and point_in_solid(shape, (p + q) * 0.5):
                        hit = p
                        break
                if hit is not None:
                    found.append((th, hit))
                    break
    found.sort(key=lambda x: x[0])
    out, used = [], []
    for th, p in found:
        if any((p - u).Length < 1.0 and abs(th - t0) < 1e-3 for u, t0 in used):
            continue
        used.append((p, th))
        if len(used) > 5:
            break
        err = th < emin - 1e-9
        req = emin if err else ewarn
        out.append(Issue(
            rule="min_wall_thickness", level="L3", severity="error" if err else "warning",
            target=fmt_pt(p), measured=round(th, 3), required=req, location=loc(p),
            message=f"壁厚 {th:.2f}mm(位于 {fmt_pt(p)} 附近),{'小于最小值' if err else '小于建议值'} {req:g}mm",
            hint=f"将该处壁厚增加到至少 {max(ewarn, req):g}mm(增加 {max(ewarn, req) - th:.2f}mm),或减小相邻孔/腔的尺寸"))
    return out


@rule("hole_spacing", "L3")
def hole_spacing(shape, spec, c):
    k = c["hole_spacing_factor"]
    hs = find_holes(shape)
    out = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            a, b = hs[i], hs[j]
            if abs(a.direction.dot(b.direction)) < 0.999:
                continue
            d = a.direction
            # perpendicular distance between parallel axes
            w = b.origin - a.origin
            perp = (w - d * w.dot(d)).Length
            if perp < 1e-3:
                continue  # coaxial (e.g. counterbore)
            # axial overlap
            a1, a2 = 0.0, a.depth
            b1 = w.dot(d)
            b2 = b1 + b.depth
            if b2 < a1 or b1 > a2:
                continue
            gap = perp - a.radius - b.radius
            need = k * min(a.diameter, b.diameter)
            if gap + 1e-6 < need:
                out.append(Issue(
                    rule="hole_spacing", level="L3", target=f"{a.id},{b.id}", location=loc((a.center + b.center) * 0.5), measured=round(gap, 3),
                    required=round(need, 3),
                    message=f"孔 {a.id} 与 {b.id} 孔间壁 {gap:.1f}mm,要求不小于 {need:.1f}mm({k:g}×较小孔径)",
                    hint=f"将两孔中心距增大至少 {need - gap:.1f}mm(当前 {perp:.1f}mm)"))
    return out


# ------------------------------------------------------------ hole_depth_ratio

@rule("hole_depth_ratio", "L3")
def hole_depth_ratio(shape, spec, c):
    warn, err, twarn = c["hole_depth_warn"], c["hole_depth_error"], c["hole_depth_through_warn"]
    out = []
    try:
        holes = find_holes(shape)
    except Exception:
        return []
    for h in holes:
        try:
            if h.diameter < 1e-6 or h.depth < 1e-6:
                continue
            ratio = h.depth / h.diameter
            if h.through:
                if ratio > twarn + 1e-9:
                    out.append(Issue(
                        rule="hole_depth_ratio", level="L3", severity="warning", target=h.id, location=loc(h.center),
                        measured=round(ratio, 2), required=twarn,
                        message=f"通孔 {h.id}(Ø{h.diameter:.1f},轴线 {fmt_pt(h.center)})穿过厚度 {h.depth:.1f}mm,"
                                f"深径比 {ratio:.1f},超过建议值 {twarn:g}",
                        hint=f"孔径增大到至少 {h.depth / twarn:.1f}mm,或减小该处板厚/改为两侧对钻,"
                             f"或确认可用深孔钻/枪钻加工"))
                continue
            lo = h.point_at(-0.01)
            hi = h.point_at(h.depth + 0.01)
            if point_in_solid(shape, lo) == point_in_solid(shape, hi):
                continue  # closed void or unrecognised
            if ratio > warn + 1e-9:
                is_err = ratio > err + 1e-9
                req = err if is_err else warn
                out.append(Issue(
                    rule="hole_depth_ratio", level="L3", severity="error" if is_err else "warning",
                    target=h.id, location=loc(h.center), measured=round(ratio, 2), required=req,
                    message=f"盲孔 {h.id}(Ø{h.diameter:.1f},轴线 {fmt_pt(h.center)})深 {h.depth:.1f}mm,"
                            f"深径比 {ratio:.1f},{'超过上限' if is_err else '超过建议值'} {req:g}",
                    hint=f"将孔深减小到不超过 {req * h.diameter:.1f}mm,或把孔径增大到至少 {h.depth / req:.1f}mm,"
                         f"或改为通孔/分段台阶孔"))
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ deep_pocket

def _pocket_wall(face, edge, adj, nF):
    """Wall face bounding a pocket floor across `edge`, or None if the junction is not a pocket wall."""
    others = [x for x in _lookup(adj, edge) if not x.wrapped.IsSame(face.wrapped)]
    if not others:
        return None
    o = others[0]
    conc = edge_is_concave(edge, face, o)
    if conc is None:
        if not _tangent_concave(o):
            return None
        # floor fillet: continue to the wall on the far side of the fillet
        for e2 in o.Edges():
            for x in _lookup(adj, e2):
                if x.wrapped.IsSame(o.wrapped) or x.wrapped.IsSame(face.wrapped):
                    continue
                if x.geomType() == "PLANE" and abs(x.normalAt().dot(nF)) < 1e-3:
                    return x
        return None
    if not conc:
        return None
    if o.geomType() == "PLANE" and abs(o.normalAt().dot(nF)) < 1e-3:
        return o
    info = cylinder_info(o)
    if info and abs(info[1].normalized().dot(nF)) > 0.999:
        return o
    return None


def _caliper_min(points, n):
    """Smallest projected extent of points over in-plane directions (minimum caliper width)."""
    ref = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
    u = n.cross(ref).normalized()
    w = n.cross(u).normalized()
    best = float("inf")
    for k in range(36):
        a = math.pi * k / 36
        d = u * math.cos(a) + w * math.sin(a)
        ps = [p.dot(d) for p in points]
        best = min(best, max(ps) - min(ps))
    return best


@rule("deep_pocket", "L3")
def deep_pocket(shape, spec, c):
    warn = c["deep_pocket_warn"]
    out = []
    try:
        adj = adjacency(shape)
        faces = shape.Faces()
    except Exception:
        return []
    for F in faces:
        try:
            if F.geomType() != "PLANE":
                continue
            nF = F.normalAt()
            edges = F.outerWire().Edges()
            walls = []
            ok = True
            for e in edges:
                w = _pocket_wall(F, e, adj, nF)
                if w is None:
                    ok = False
                    break
                if not any(w.wrapped.IsSame(x.wrapped) for x in walls):
                    walls.append(w)
            if not ok or len(walls) < 3:
                continue
            if any(is_hole_face(w) for w in walls):
                continue  # round blind hole: handled by hole_depth_ratio
            p0 = F.Center()
            depth = min(max(nF.dot(V(*v.toTuple()) - p0) for v in w.Vertices()) for w in walls)
            if depth <= 1e-6:
                continue
            pts = []
            for e in edges:
                pts += [e.positionAt(t / 8) for t in range(8)]
            width = _caliper_min(pts, nF)
            # opposite planar wall pairs give the narrow arms of non-convex pockets
            pl = [w for w in walls if w.geomType() == "PLANE"]
            for i in range(len(pl)):
                for j in range(i + 1, len(pl)):
                    a, b = pl[i], pl[j]
                    if a.normalAt().dot(b.normalAt()) > -0.999:
                        continue
                    t = nF.cross(a.normalAt())
                    ra = [t.dot(V(*v.toTuple())) for v in a.Vertices()]
                    rb = [t.dot(V(*v.toTuple())) for v in b.Vertices()]
                    if min(max(ra), max(rb)) - max(min(ra), min(rb)) < 1e-3:
                        continue
                    width = min(width, abs((a.Center() - b.Center()).dot(a.normalAt())))
            if width < 1e-6:
                continue
            ratio = depth / width
            if ratio > warn + 1e-9:
                out.append(Issue(
                    rule="deep_pocket", level="L3", severity="warning", target=fmt_pt(p0), location=loc(p0),
                    measured=round(ratio, 2), required=warn,
                    message=f"深腔(底面位于 {fmt_pt(p0)} 附近)深 {depth:.1f}mm,最小腔宽 {width:.1f}mm,"
                            f"深宽比 {ratio:.1f},超过建议值 {warn:g}",
                    hint=f"将腔深减小到不超过 {warn * width:.1f}mm,或把最小腔宽增大到至少 {depth / warn:.1f}mm,"
                         f"或改为从两侧加工/分体设计"))
        except Exception:
            continue
    out.sort(key=lambda i: -i.measured)
    return out[:5]


# --------------------------------------------------------------- thin_web_height

@rule("thin_web_height", "L3")
def thin_web_height(shape, spec, c):
    warn, tmax = c["thin_web_warn"], c["thin_web_max_thickness"]
    out = []
    try:
        adj = adjacency(shape)
        faces = shape.Faces()
    except Exception:
        return []

    def base_height(X, T, nT, pT):
        hs = []
        for e in X.outerWire().Edges():
            others = [x for x in _lookup(adj, e) if not x.wrapped.IsSame(X.wrapped)]
            if not others:
                continue
            o = others[0]
            if e.geomType() != "LINE" or abs(e.tangentAt(0.5).normalized().dot(nT)) > 0.1:
                continue
            cc = edge_is_concave(e, X, o)
            if cc is True or (cc is None and _tangent_concave(o)):
                hs.append((pT - e.positionAt(0.5)).dot(nT))
        return max(hs) if hs else None

    for T in faces:
        try:
            if T.geomType() != "PLANE":
                continue
            nT, pT = T.normalAt(), T.Center()
            nbs = []
            for e in T.outerWire().Edges():
                for x in _lookup(adj, e):
                    if x.wrapped.IsSame(T.wrapped) or x.geomType() != "PLANE":
                        continue
                    if abs(x.normalAt().dot(nT)) < 1e-3 and edge_is_concave(e, T, x) is False:
                        nbs.append(x)
            for i in range(len(nbs)):
                for j in range(i + 1, len(nbs)):
                    A, B = nbs[i], nbs[j]
                    nA = A.normalAt()
                    if nA.dot(B.normalAt()) > -0.999:
                        continue
                    th = abs((A.Center() - B.Center()).dot(nA))
                    if th < 1e-3 or th > tmax + 1e-9:
                        continue
                    ext = [nA.dot(V(*v.toTuple())) for v in T.Vertices()]
                    if abs(max(ext) - min(ext) - th) > 1e-3:
                        continue
                    hs = [h for h in (base_height(A, T, nT, pT), base_height(B, T, nT, pT)) if h is not None]
                    if not hs:
                        continue
                    H = min(hs)
                    ratio = H / th
                    if ratio > warn + 1e-9:
                        out.append(Issue(
                            rule="thin_web_height", level="L3", severity="warning", target=fmt_pt(pT), location=loc(pT),
                            measured=round(ratio, 2), required=warn,
                            message=f"薄筋/薄壁(顶面位于 {fmt_pt(pT)} 附近)高 {H:.1f}mm,厚 {th:.1f}mm,"
                                    f"高厚比 {ratio:.1f},超过建议值 {warn:g}(加工易振刀、变形)",
                            hint=f"将厚度增加到至少 {H / warn:.1f}mm,或把高度降到不超过 {warn * th:.1f}mm,"
                                 f"或在根部加圆角/增设加强筋"))
        except Exception:
            continue
    out.sort(key=lambda i: -i.measured)
    return out[:5]
