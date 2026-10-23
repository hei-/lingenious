"""Three-view engineering drawing (third-angle, A3 landscape) from a CadQuery solid.

    draw(shape, out_dir, name="part", material="") -> {"dxf", "pdf", "png", "holes", ...}

Dimensions are drawn as clean line+text (layer DIM / TEXT), not DXF DIMENSION entities, so the
DXF and the matplotlib PDF render identically.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cadquery as cq

from .feat import axis_view, exact_bbox, find_slots, front_section, pair_counterbores
from .hlr import project_views
from .layout import Placer, hatch_lines, text_bbox
from .sheet import Sheet

__all__ = ["draw"]

SW, SH = 420.0, 297.0
OV = 20.0            # offset of overall dimension lines from the view
GAP = 32.0           # gap between views
X0, Y0 = 43.0, 76.0  # lower-left of front view
TB = (270.0, 10.0, 410.0, 50.0)  # title block
TXT = 3.0
SCALES = [50, 20, 10, 5, 2, 1, 1 / 2, 1 / 5, 1 / 10, 1 / 20, 1 / 50, 1 / 100, 1 / 200, 1 / 500]


def _n(v: float) -> str:
    return f"{round(v, 1):g}"


# ------------------------------------------------------------------ dimensions
def _arrow(sh, tip, direction):
    dx, dy = direction
    px, py = -dy, dx
    b = (tip[0] + dx * 3, tip[1] + dy * 3)
    sh.poly("DIM", [(b[0] + px * 0.9, b[1] + py * 0.9), tip, (b[0] - px * 0.9, b[1] - py * 0.9)])


def hdim(sh, xa, xb, yref, ydim, text):
    """Horizontal linear dimension; yref = feature edge, ydim = dim line level."""
    s = 1 if ydim > yref else -1
    for x in (xa, xb):
        sh.line("DIM", (x, yref + s * 1.5), (x, ydim + s * 1.5))
    sh.line("DIM", (xa, ydim), (xb, ydim))
    d = 1 if xb >= xa else -1
    _arrow(sh, (xa, ydim), (d, 0))
    _arrow(sh, (xb, ydim), (-d, 0))
    sh.text("TEXT", (xa + xb) / 2, ydim + 1.2, text, TXT, 0, "C")


def vdim(sh, ya, yb, xref, xdim, text):
    s = 1 if xdim > xref else -1
    for y in (ya, yb):
        sh.line("DIM", (xref + s * 1.5, y), (xdim + s * 1.5, y))
    sh.line("DIM", (xdim, ya), (xdim, yb))
    d = 1 if yb >= ya else -1
    _arrow(sh, (xdim, ya), (0, d))
    _arrow(sh, (xdim, yb), (0, -d))
    sh.text("TEXT", xdim - 1.2, (ya + yb) / 2, text, TXT, 90, "C")


# ------------------------------------------------------------------ features
def _label(it):
    dep = "" if it["through"] else f" ↧{_n(it['depth'])}"
    if it["kind"] == "slot":
        return f"{_n(it['length'])}×{_n(it['d'])}{dep}"
    if it["kind"] == "cbore":
        return f"Ø{_n(it['d'])}{dep} ⌴ Ø{_n(it['D'])} ↧{_n(it['depth_c'])}"
    return f"Ø{_n(it['d'])}{dep}"


def _group_items(items):
    groups: dict = {}
    for it in items:
        key = (it["kind"], round(it["d"], 2), round(it["D"] or 0, 2), round(it["depth_c"], 1),
               it["through"], 0.0 if it["through"] else round(it["depth"], 1), round(it["length"] or 0, 1))
        groups.setdefault(key, []).append(it)
    out = []
    for i, (key, its) in enumerate(groups.items()):
        tag = chr(ord("A") + i) if i < 26 else f"H{i + 1}"
        it = its[0]
        thr = "THRU" if it["through"] else f"BLIND, DEPTH {_n(it['depth'])}"
        if it["kind"] == "slot":
            dia, typ = f"{_n(it['length'])}×{_n(it['d'])}", "SLOT " + thr
        elif it["kind"] == "cbore":
            dia, typ = f"Ø{_n(it['d'])}", f"{thr}, ⌴ Ø{_n(it['D'])} ↧{_n(it['depth_c'])}"
        else:
            dia, typ = f"Ø{_n(it['d'])}", thr
        if axis_view(it["direction"]) is None:
            d = it["direction"]
            typ += f", AXIS ({d.x:.2f},{d.y:.2f},{d.z:.2f})"
        out.append(dict(tag=tag, items=its, label=_label(it), dia=dia, typ=typ, kind=it["kind"]))
        for x in its:
            x["tag"] = tag
    return out


def _ray_exit(c, u, a, b, r):
    """Distance t along unit u from c at which the point leaves the obround (segment a-b, radius r)."""
    def dist(p):
        ab = (b[0] - a[0], b[1] - a[1])
        L2 = ab[0] ** 2 + ab[1] ** 2
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
        return math.hypot(p[0] - a[0] - t * ab[0], p[1] - a[1] - t * ab[1])
    lo, hi = 0.0, r + math.dist(a, b) + 1
    for _ in range(30):
        m = (lo + hi) / 2
        if dist((c[0] + u[0] * m, c[1] + u[1] * m)) <= r:
            lo = m
        else:
            hi = m
    return hi


_ANGLES = [45, 135, -45, -135, 20, 160, -20, -160, 75, 105, -75, -105, 0, 180, 90, -90]


# ------------------------------------------------------------------ main
def draw(shape: cq.Shape, out_dir: Path, name: str = "part", material: str = "") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ebb = exact_bbox(shape)
    W, D, H = max(ebb[3] - ebb[0], 1e-6), max(ebb[4] - ebb[1], 1e-6), max(ebb[5] - ebb[2], 1e-6)
    mn = {"x": ebb[0], "y": ebb[1], "z": ebb[2]}

    try:
        from core.checks.features import find_holes
        holes = list(find_holes(shape))
    except Exception:
        holes = []
    try:
        items = pair_counterbores(holes)
    except Exception:
        items = []
    try:
        slots = find_slots(shape)
    except Exception:
        slots = []
    items += slots
    items.sort(key=lambda it: (it["kind"], round(it["d"], 2), round(it["center"].x, 2),
                               round(it["center"].y, 2), round(it["center"].z, 2)))
    groups = _group_items(items)
    for it in items:
        it["view"] = axis_view(it["direction"])
    oblique = [g for g in groups if any(i["view"] is None for i in g["items"])]

    views, used_hlr = project_views(shape)

    # section candidate: first counterbore / blind hole whose axis is X or Z
    sec_item = next((i for k in ("cbore", "hole") for i in items
                     if i["kind"] == k and (k == "cbore" or not i["through"])
                     and i["view"] in ("top", "right")), None)

    # table geometry (top-right)
    tw, rh = 130.0, 6.0
    th = rh * (len(groups) + 2) if groups else 0.0
    table = (SW - 12 - tw, SH - 12 - th, SW - 12, SH - 12) if groups else None

    avail_w = SW - 15 - X0 - GAP
    avail_h = SH - 15 - Y0 - GAP
    fit = min(avail_w / (W + D), avail_h / (H + D))
    cands = [s for s in SCALES if s <= fit + 1e-9] or [fit]

    def rects(s):
        return {
            "front": (X0, Y0, X0 + W * s, Y0 + H * s),
            "top": (X0, Y0 + H * s + GAP, X0 + W * s, Y0 + H * s + GAP + D * s),
            "right": (X0 + W * s + GAP, Y0, X0 + W * s + GAP + D * s, Y0 + H * s),
        }

    def overlaps(a, b, pad=8):
        return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])

    scale = cands[-1]
    for s in cands:
        r = rects(s)
        if table is None or not (overlaps(r["top"], table) or overlaps(r["right"], table)):
            scale = s
            break
    s = scale
    R = rects(s)

    # model 2D -> sheet
    org = {
        "front": (R["front"][0] - mn["x"] * s, R["front"][1] - mn["z"] * s),
        "top": (R["top"][0] - mn["x"] * s, R["top"][1] - mn["y"] * s),
        "right": (R["right"][0] - mn["y"] * s, R["right"][1] - mn["z"] * s),
    }

    def P(view, a, b):
        ox, oy = org[view]
        return (ox + a * s, oy + b * s)

    sh = Sheet(SW, SH)
    pl = Placer((8, 8, SW - 8, SH - 8))
    sh.rect("FRAME", 5, 5, SW - 5, SH - 5)
    for v, data in views.items():
        for pp in data["hidden"]:
            sh.poly("HIDDEN", [P(v, a, b) for a, b in pp])
    for v, data in views.items():
        for pp in data["visible"]:
            q = [P(v, a, b) for a, b in pp]
            sh.poly("VISIBLE", q)
            pl.add_geom([q])

    # keep-out: table, title block
    if table:
        pl.add_box((table[0], table[1] - 12, table[2], table[3]))
    pl.add_box(TB)

    # overall dimensions
    f, t, r_ = R["front"], R["top"], R["right"]
    hdim(sh, f[0], f[2], f[1], f[1] - OV, _n(W))
    vdim(sh, f[1], f[3], f[0], f[0] - OV, _n(H))
    vdim(sh, t[1], t[3], t[0], t[0] - OV, _n(D))
    hdim(sh, r_[0], r_[2], r_[1], r_[1] - OV, _n(D))
    pl.absorb(sh)

    # section A-A (front section through the axis of the first counterbore / blind hole)
    section: Any = None
    if sec_item is not None:
        cy = sec_item["center"].y
        try:
            section = front_section(shape, cy, ebb)
        except Exception:
            section = None
    sec_rect: Any = None
    if section is not None:
        keep = [R["front"], R["top"], R["right"]] + ([(table[0], table[1] - 14, table[2], table[3])] if table else []) + [TB]
        for sx0, sy0 in ((R["right"][2] + GAP, Y0), (R["top"][2] + GAP, R["top"][1]),
                         (R["right"][2] + GAP, R["right"][3] + GAP)):
            cand = (sx0, sy0, sx0 + W * s, sy0 + H * s)
            if cand[2] <= SW - 15 and cand[3] <= SH - 15 and not any(overlaps(cand, k, 12) for k in keep):
                sec_rect = cand
                break
        if sec_rect is None:
            section = None
    if section is not None:
        vis, loops = section
        T = lambda p: (sec_rect[0] + (p[0] - mn["x"]) * s, sec_rect[1] + (p[1] - mn["z"]) * s)
        for pp in vis:
            sh.poly("VISIBLE", [T(p) for p in pp])
        sloops = [[T(p) for p in lp] for lp in loops]
        for a, b in hatch_lines(sloops, 2.5):
            sh.line("HATCH", a, b)
        sh.text("TEXT", (sec_rect[0] + sec_rect[2]) / 2, sec_rect[1] - 9, "SECTION A-A", 4.0, 0, "C")
        # cutting-plane marks in the top view
        ycut = P("top", 0, cy)[1]
        x0_, x1_ = t[0], t[2]
        sh.line("CENTER", (x0_ - 4, ycut), (x1_ + 4, ycut))
        for xe, sgn in ((x0_ - 4, -1), (x1_ + 4, 1)):
            sh.line("VISIBLE", (xe, ycut), (xe + sgn * 6, ycut))
            pl.segs.append(((xe, ycut), (xe + sgn * 6, ycut)))
            sh.line("DIM", (xe + sgn * 6, ycut), (xe + sgn * 6, ycut + 7))
            _arrow(sh, (xe + sgn * 6, ycut + 7), (0, -1))
            sh.text("TEXT", xe + sgn * 6, ycut + 9.5, "A", 3.5, 0, "C")
        pl.absorb(sh)

    # hole / slot annotation
    axes = {"front": ("x", "z"), "top": ("x", "y"), "right": ("y", "z")}
    for v in ("front", "top", "right"):
        vis_items = [i for i in items if i["view"] == v]
        if not vis_items:
            continue
        ha, va = axes[v]
        rect = R[v]
        centers = []
        for it in vis_items:
            def proj(c, ha=ha, va=va):
                wc = {"x": c.x, "y": c.y, "z": c.z}
                return P(v, wc[ha], wc[va])
            sx, sy = proj(it["center"])
            centers.append((it, sx, sy, proj(it["a"]), proj(it["b"])))
            rr = (it["length"] / 2 if it["kind"] == "slot" else it["r"]) * s
            k = min(rr * 1.3, rr + 3)
            sh.line("CENTER", (sx - k, sy), (sx + k, sy))
            sh.line("CENTER", (sx, sy - k), (sx, sy + k))
        pl.absorb(sh)
        # ordinate dimensions from the view's lower-left corner, greedy level choice
        cbx: dict = {}
        cby: dict = {}
        for it, sx, sy, _, _ in centers:
            cbx.setdefault(round(sx, 1), (sx, sy))
            cby.setdefault(round(sy, 1), (sy, sx))
        for key in sorted(cbx):
            x, y0 = cbx[key]
            best: Any = None
            for lvl in range(7):
                yl = rect[1] - 5 - 4.5 * lvl
                tx = _n((x - rect[0]) / s)
                box = text_bbox(x, yl - 3.6, tx, 2.6, 0, "C")
                c = pl.box_cost(box, geom=False) + pl.seg_cost((x, y0), (x, yl), geom=False) * 0.5 + lvl * 0.01
                if best is None or c < best[0]:
                    best = (c, yl, tx)
                if c < 0.1:
                    break
            _, yl, tx = best
            sh.line("DIM", (x, y0), (x, yl))
            sh.text("TEXT", x, yl - 3.6, tx, 2.6, 0, "C")
            pl.absorb(sh)
        for key in sorted(cby):
            y, x0 = cby[key]
            best = None
            for lvl in range(7):
                xl = rect[0] - 5 - 4.5 * lvl
                tx = _n((y - rect[1]) / s)
                box = text_bbox(xl - 1.0, y, tx, 2.6, 90, "C")
                c = pl.box_cost(box, geom=False) + pl.seg_cost((x0, y), (xl, y), geom=False) * 0.5 + lvl * 0.01
                if best is None or c < best[0]:
                    best = (c, xl, tx)
                if c < 0.1:
                    break
            _, xl, tx = best
            sh.line("DIM", (x0, y), (xl, y))
            sh.text("TEXT", xl - 1.0, y, tx, 2.6, 90, "C")
            pl.absorb(sh)
        # leader + label, once per group in this view, collision-avoiding
        done = set()
        for it, _, _, _, _ in centers:
            tag = it["tag"]
            if tag in done:
                continue
            done.add(tag)
            g = next(g for g in groups if g["tag"] == tag)
            qty = sum(1 for o, *_ in centers if o["tag"] == tag)
            lab = f"{tag} " + (f"{qty}x " if qty > 1 else "") + g["label"]
            cand_items = [c for c in centers if c[0]["tag"] == tag][:6]
            best = None
            for ext in (7, 12, 18, 26, 36):
                for (o, sx, sy, a, b) in cand_items:
                    left = sx < (rect[0] + rect[2]) / 2
                    angs = sorted(_ANGLES, key=lambda x: (math.cos(math.radians(x)) >= 0) == left)
                    rr = (o["D"] / 2 if o["kind"] == "cbore" else o["r"]) * s
                    for ang in angs:
                        u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
                        t0 = _ray_exit((sx, sy), u, a, b, rr)
                        p0 = (sx + u[0] * t0, sy + u[1] * t0)
                        p1 = (sx + u[0] * (t0 + ext), sy + u[1] * (t0 + ext))
                        side = -1 if (u[0] < -1e-6 or (abs(u[0]) <= 1e-6 and left)) else 1
                        p2 = (p1[0] + 6 * side, p1[1])
                        box = text_bbox(p2[0] + side, p2[1] + 0.8, lab, TXT, 0, "R" if side < 0 else "L")
                        ps = (p0[0] + u[0] * 0.8, p0[1] + u[1] * 0.8)
                        c = (pl.box_cost(box) + pl.seg_cost(ps, p1) + pl.seg_cost(p1, p2)
                             + ext * 0.01)
                        if best is None or c < best[0] - 1e-9:
                            best = (c, p0, p1, p2, side, box)
                        if c < 0.5:
                            break
                    if best[0] < 0.5:
                        break
                if best[0] < 0.5:
                    break
            _, p0, p1, p2, side, box = best
            sh.poly("DIM", [p0, p1, p2])
            sh.text("TEXT", p2[0] + side, p2[1] + 0.8, lab, TXT, 0, "R" if side < 0 else "L")
            pl.absorb(sh)

    # hole table
    if table:
        x1, y1, x2, y2 = table
        cols = [x1, x1 + 10, x1 + 55, x1 + 68, x2]
        sh.rect("FRAME", x1, y1, x2, y2)
        sh.text("TEXT", (x1 + x2) / 2, y2 - 4.3, "HOLE TABLE", 3.2, 0, "C")
        rows = [("ID", "DIA", "QTY", "TYPE")] + [
            (g["tag"], g["dia"], str(len(g["items"])), g["typ"]) for g in groups]
        for ri, row in enumerate(rows):
            ytop = y2 - rh * (ri + 1)
            sh.line("FRAME", (x1, ytop), (x2, ytop))
            for ci, cell in enumerate(row):
                sh.text("TEXT", cols[ci] + 1.5, ytop - rh + 1.8, cell, 2.8, 0, "L")
        for cx in cols[1:-1]:
            sh.line("FRAME", (cx, y1), (cx, y2 - rh))
        if oblique:
            tags = ",".join(g["tag"] for g in oblique)
            sh.text("TEXT", x1, y1 - 5, f"NOTE: AXIS OF {tags} NOT ALONG X/Y/Z - SEE HOLE TABLE", 2.6, 0, "L")
        if section is not None:
            sh.text("TEXT", x1, y1 - (10 if oblique else 5), "SECTION A-A: CUT THROUGH FIRST CBORE/BLIND HOLE AXIS", 2.6, 0, "L")

    # title block
    x1, y1, x2, y2 = TB
    sh.rect("FRAME", x1, y1, x2, y2)
    ym = y1 + 20
    sh.line("FRAME", (x1, ym), (x2, ym))
    sh.line("FRAME", (x1 + 30, y1), (x1 + 30, ym))
    sh.line("FRAME", (x1 + 80, y1), (x1 + 80, ym))
    sh.text("TEXT", x1 + 2, y2 - 4, "PART", 2.2)
    nm = name or "part"
    sh.text("TEXT", x1 + 4, ym + 4.5, nm, 5.0 if len(nm) <= 26 else max(2.8, 130 / len(nm) / 1.1))
    sh.text("TEXT", x1 + 2, ym - 4, "SCALE", 2.2)
    sc = f"{_n(s)}:1" if s >= 1 else f"1:{_n(1 / s)}"
    sh.text("TEXT", x1 + 4, y1 + 5, sc, 5.0)
    sh.text("TEXT", x1 + 32, ym - 4, "MATERIAL", 2.2)
    sh.text("TEXT", x1 + 34, y1 + 6, material or "-", 3.5 if len(material) <= 14 else 2.6)
    # projection symbol (frustum side view at left, concentric circles at right)
    sx, sy = x1 + 85, y1 + 3
    sh.poly("VISIBLE", [(sx, sy + 2), (sx + 9, sy + 4), (sx + 9, sy + 10), (sx, sy + 12)], closed=True)
    sh.line("CENTER", (sx - 2, sy + 7), (sx + 24, sy + 7))
    sh.circle("VISIBLE", sx + 17, sy + 7, 5)
    sh.circle("VISIBLE", sx + 17, sy + 7, 2.5)
    sh.text("TEXT", x1 + 82, ym - 4, "THIRD ANGLE PROJECTION", 2.2)
    sh.text("TEXT", x1 + 112, y1 + 3, "UNITS: mm", 2.4)

    dxf, pdf, png = out_dir / "drawing.dxf", out_dir / "drawing.pdf", out_dir / "drawing.png"
    sh.write_dxf(dxf)
    sh.write_pdf(pdf, png)
    return {"dxf": dxf, "pdf": pdf, "png": png, "holes": len(holes), "hole_groups": len(groups),
            "scale": s, "hlr": used_hlr, "slots": len(slots),
            "counterbores": sum(1 for i in items if i["kind"] == "cbore"),
            "oblique_groups": len(oblique), "section": section is not None}
