"""Layout helpers: text boxes, greedy collision bookkeeping, section hatch lines."""
from __future__ import annotations

import math


def text_bbox(x, y, s, h, rot=0.0, align="L"):
    """Conservative axis-aligned box (x0, y0, x1, y1) of a sheet text primitive."""
    w = 0.0
    for ch in str(s):
        w += h * (1.0 if ord(ch) >= 0x2E80 else 0.7 if ord(ch) >= 0x2190 or ch == "Ø" else 0.58)
    x0 = {"L": 0.0, "C": -w / 2, "R": -w}[align]
    pts = [(x0, -0.2 * h), (x0 + w, -0.2 * h), (x0 + w, 0.8 * h), (x0, 0.8 * h)]
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    rp = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    xs, ys = [p[0] for p in rp], [p[1] for p in rp]
    return (min(xs), min(ys), max(xs), max(ys))


def boxes_overlap(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def seg_cross(p, q, r, s):
    d1, d2 = _ccw(p, q, r), _ccw(p, q, s)
    d3, d4 = _ccw(r, s, p), _ccw(r, s, q)
    return d1 * d2 < 0 and d3 * d4 < 0


def seg_hits_box(p, q, b):
    inside = lambda t: b[0] < t[0] < b[2] and b[1] < t[1] < b[3]
    if inside(p) or inside(q):
        return True
    c = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
    return any(seg_cross(p, q, c[i], c[(i + 1) % 4]) for i in range(4))


class Placer:
    """Greedy placement bookkeeping: placed text boxes, annotation segments, geometry segments."""

    CELL = 10.0

    def __init__(self, bounds):
        self.bounds = bounds
        self.boxes: list = []
        self.segs: list = []
        self.geom: dict = {}
        self._seen = {"polys": 0, "texts": 0}

    # -- registration
    def add_geom(self, polylines):
        for pl in polylines:
            for p, q in zip(pl, pl[1:]):
                x0, x1 = sorted((p[0], q[0]))
                y0, y1 = sorted((p[1], q[1]))
                for cx in range(int(x0 // self.CELL), int(x1 // self.CELL) + 1):
                    for cy in range(int(y0 // self.CELL), int(y1 // self.CELL) + 1):
                        self.geom.setdefault((cx, cy), []).append((p, q))

    def absorb(self, sheet):
        """Register everything added to the sheet since the last call (text boxes + non-geometry lines)."""
        for layer, pts in sheet.polys[self._seen["polys"]:]:
            if layer in ("DIM", "CENTER", "FRAME"):
                self.segs += list(zip(pts, pts[1:]))
        for layer, x, y, s, h, rot, a in sheet.texts[self._seen["texts"]:]:
            self.boxes.append(text_bbox(x, y, s, h, rot, a))
        self._seen = {"polys": len(sheet.polys), "texts": len(sheet.texts)}

    def add_box(self, b):
        self.boxes.append(b)

    def _geom_near(self, x0, y0, x1, y1):
        seen = set()
        for cx in range(int(x0 // self.CELL), int(x1 // self.CELL) + 1):
            for cy in range(int(y0 // self.CELL), int(y1 // self.CELL) + 1):
                for sg in self.geom.get((cx, cy), ()):
                    if id(sg) not in seen:
                        seen.add(id(sg))
                        yield sg

    # -- costs
    def box_cost(self, b, geom=True):
        c = 0.0
        bd = self.bounds
        if b[0] < bd[0] or b[1] < bd[1] or b[2] > bd[2] or b[3] > bd[3]:
            c += 50
        for o in self.boxes:
            if boxes_overlap(b, o, 0.4):
                c += 10
        for p, q in self.segs:
            if seg_hits_box(p, q, b):
                c += 6
        if geom:
            for p, q in self._geom_near(*b):
                if seg_hits_box(p, q, b):
                    c += 4
        return c

    def seg_cost(self, p, q, geom=True):
        c = 0.0
        for o in self.boxes:
            if seg_hits_box(p, q, o):
                c += 10
        for r, s in self.segs:
            if seg_cross(p, q, r, s):
                c += 3
        if geom:
            for r, s in self._geom_near(min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])):
                if seg_cross(p, q, r, s):
                    c += 1.5
        return c


def hatch_lines(loops, spacing=2.5, angle=45.0):
    """Even-odd hatch of closed polygon loops with parallel lines; returns [((x1,y1),(x2,y2)), ...]."""
    a = math.radians(angle)
    d = (math.cos(a), math.sin(a))
    n = (-d[1], d[0])
    pts = [p for lp in loops for p in lp]
    if not pts:
        return []
    cs = [n[0] * p[0] + n[1] * p[1] for p in pts]
    out = []
    k0, k1 = math.ceil(min(cs) / spacing), math.floor(max(cs) / spacing)
    for k in range(k0, k1 + 1):
        c = k * spacing + 1e-4
        ts = []
        for lp in loops:
            m = len(lp)
            for i in range(m):
                p, q = lp[i], lp[(i + 1) % m]
                cp, cq_ = n[0] * p[0] + n[1] * p[1], n[0] * q[0] + n[1] * q[1]
                if (cp <= c) != (cq_ <= c):
                    t = (c - cp) / (cq_ - cp)
                    x, y = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
                    ts.append(d[0] * x + d[1] * y)
        ts.sort()
        for i in range(0, len(ts) - 1, 2):
            t0, t1 = ts[i], ts[i + 1]
            if t1 - t0 > 0.3:
                out.append(((n[0] * c + d[0] * t0, n[1] * c + d[1] * t0), (n[0] * c + d[0] * t1, n[1] * c + d[1] * t1)))
    return out
