"""L2: conformance to PartSpec.assertions. Rules whose assertion is empty are skipped."""
from __future__ import annotations

from core.models import Issue
from .base import rule
from .features import find_breakouts, find_holes, fmt_pt, loc


@rule("bbox_match", "L2")
def bbox_match(shape, spec, c):
    b = spec.assertions.bbox
    if b is None:
        return []
    bb = shape.BoundingBox()
    got = {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen}
    out = []
    for ax in "xyz":
        want = getattr(b, ax)
        if abs(got[ax] - want) > b.tol:
            diff = want - got[ax]
            out.append(Issue(
                rule="bbox_match", level="L2", target=ax, measured=round(got[ax], 4), required=want,
                message=f"包围盒 {ax.upper()} 向尺寸为 {got[ax]:.2f}mm,要求 {want:.2f}mm(容差 ±{b.tol}mm)",
                hint=f"将 {ax.upper()} 向总尺寸{'增大' if diff > 0 else '减小'} {abs(diff):.2f}mm;"
                     f"同时确认零件朝向(X/Y/Z 轴方向)与规格一致"))
    return out


@rule("hole_count", "L2")
def hole_count(shape, spec, c):
    want = spec.assertions.hole_count
    if want is None:
        return []
    holes = find_holes(shape)
    n = len(holes)
    if n == want:
        return []
    diff = want - n
    return [Issue(rule="hole_count", level="L2", measured=float(n), required=float(want),
                  message=f"模型有 {n} 个孔,要求 {want} 个",
                  hint=f"{'补充' if diff > 0 else '删除'} {abs(diff)} 个孔;"
                       f"当前孔径: {', '.join(f'{h.diameter:.2f}' for h in holes) or '无'}mm")]


def _match(want: list[float], got: list[float], tol: float):
    """Greedy multiset match on sorted lists. Returns (unmatched_want, unmatched_got)."""
    got = sorted(got)
    left = []
    for w in sorted(want):
        best = None
        for i, g in enumerate(got):
            if abs(g - w) <= tol and (best is None or abs(g - w) < abs(got[best] - w)):
                best = i
        if best is None:
            left.append(w)
        else:
            got.pop(best)
    return left, got


@rule("hole_diameter", "L2")
def hole_diameter(shape, spec, c):
    a = spec.assertions
    if not a.hole_diameters:
        return []
    got = [h.diameter for h in find_holes(shape)]
    miss, extra = _match(a.hole_diameters, got, a.diameter_tol)
    if not miss and not extra:
        return []
    # only complain about extras if the spec lists a full set (count matches or unspecified count)
    if a.hole_count is not None and a.hole_count != len(a.hole_diameters):
        extra = []
    if not miss and not extra:
        return []
    fmt = lambda xs: ", ".join(f"{x:.2f}" for x in xs) or "无"
    return [Issue(rule="hole_diameter", level="L2",
                  message=f"孔径不符:要求 [{fmt(sorted(a.hole_diameters))}]mm(容差 ±{a.diameter_tol}mm),"
                          f"实际 [{fmt(sorted(got))}]mm;缺少 [{fmt(miss)}],多余 [{fmt(extra)}]",
                  hint=f"调整孔径使其匹配要求;缺少的直径: {fmt(miss)}mm,多余的直径: {fmt(extra)}mm")]


@rule("volume_range", "L2")
def volume_range(shape, spec, c):
    vr = spec.assertions.volume_range
    if not vr:
        return []
    lo, hi = vr
    if lo is None and hi is None:
        return []
    v = shape.Volume()
    if lo is not None and v < lo:
        return [Issue(rule="volume_range", level="L2", measured=round(v, 2), required=lo,
                      message=f"体积 {v:.1f}mm³ 小于下限 {lo:.1f}mm³",
                      hint=f"体积偏小 {lo - v:.1f}mm³:检查是否多切了材料或尺寸偏小")]
    if hi is not None and v > hi:
        return [Issue(rule="volume_range", level="L2", measured=round(v, 2), required=hi,
                      message=f"体积 {v:.1f}mm³ 大于上限 {hi:.1f}mm³",
                      hint=f"体积偏大 {v - hi:.1f}mm³:检查是否漏切孔/腔或尺寸偏大")]
    return []


@rule("hole_breakout", "L2")
def hole_breakout(shape, spec, c):
    """Always on (not driven by assertions): a hole/slot cut through an outer edge leaves a notch."""
    out = []
    for i, b in enumerate(find_breakouts(shape), 1):
        d, p, ed = b["diameter"], b["center"], b["edge_dist"]
        need = min(c["hole_edge_factor"] * d, d / 2 + c.get("hole_edge_wall_cap", 6.0))
        ed_txt = f"{ed:.1f}mm" if ed is not None else "未知"
        shift = (need - ed) if ed is not None else need
        out.append(Issue(
            rule="hole_breakout", level="L2", severity="error", target=f"breakout{i}", location=loc(p),
            measured=None if ed is None else round(ed, 3), required=round(need, 3),
            message=f"孔 Ø{d:.1f} 在 {fmt_pt(p)} 处与板边/板面相交,形成缺口或开槽,孔中心距边缘 {ed_txt}"
                    f"(要求孔应完整落在材料内,中心距边缘至少 {need:.1f}mm)",
            hint=f"将孔中心移至距边缘至少 {need:.1f}mm 处(需再向内移动约 {max(shift, 0):.1f}mm),"
                 f"并确认孔的开孔方向与工作平面正确(孔轴应垂直于要打孔的板面,孔位在该板面中心)"))
    return out


def _axis_of(h):
    d = h.direction
    comps = [abs(d.x), abs(d.y), abs(d.z)]
    i = max(range(3), key=lambda k: comps[k])
    return "XYZ"[i] if comps[i] > 0.999 else None


@rule("hole_position", "L2")
def hole_position(shape, spec, c):
    """Hole axes vs expected positions in the shared frame (XY bbox centre, Z from bbox bottom)."""
    want = spec.assertions.hole_positions
    if not want:
        return []
    bb = shape.BoundingBox()
    ref = {"X": (bb.xmin + bb.xmax) / 2, "Y": (bb.ymin + bb.ymax) / 2, "Z": bb.zmin}
    found = []
    for h in find_holes(shape):
        ax = _axis_of(h)
        if ax is None:
            continue
        o = h.origin
        found.append((h, ax, {"X": o.x - ref["X"], "Y": o.y - ref["Y"], "Z": o.z - ref["Z"]}))

    def dev(w, f):
        _, ax, pos = f
        return max([abs(pos[k] - v) for k, v in (("X", w.x), ("Y", w.y), ("Z", w.z)) if v is not None and k != w.axis]
                   or [0.0])

    dtol = spec.assertions.diameter_tol
    pairs = sorted(((dev(w, f), wi, fi) for wi, w in enumerate(want) for fi, f in enumerate(found)
                    if f[1] == w.axis and abs(f[0].diameter - w.diameter) <= dtol and dev(w, f) <= w.tol),
                   key=lambda t: t[0])
    used_w, used_f = set(), set()
    for d, wi, fi in pairs:
        if wi not in used_w and fi not in used_f:
            used_w.add(wi)
            used_f.add(fi)
    out = []
    for wi, w in enumerate(want):
        if wi in used_w:
            continue
        exp = ", ".join(f"{k}={v:g}" for k, v in (("X", w.x), ("Y", w.y), ("Z", w.z)) if v is not None and k != w.axis)
        cands = [(dev(w, f), f) for fi, f in enumerate(found)
                 if fi not in used_f and f[1] == w.axis and abs(f[0].diameter - w.diameter) <= dtol]
        if not cands:
            out.append(Issue(rule="hole_position", level="L2", target=f"hole{wi + 1}",
                             message=f"未找到 Ø{w.diameter:g} 的 {w.axis} 向孔(期望孔轴位置 {exp})",
                             hint="确认该孔存在、孔径与孔轴方向正确;孔位用绝对坐标(原点=零件XY中心)建模,"
                                  "不要在叠加特征后用 faces('>Z').workplane() 打孔"))
            continue
        dv, f = min(cands, key=lambda t: t[0])
        got = ", ".join(f"{k}={f[2][k]:.1f}" for k in "XYZ" if k != w.axis
                        and {"X": w.x, "Y": w.y, "Z": w.z}[k] is not None)
        out.append(Issue(
            rule="hole_position", level="L2", target=f"hole{wi + 1}", location=loc(f[0].center), measured=round(dv, 3), required=w.tol,
            message=f"Ø{w.diameter:g} 孔位置不符:期望 ({exp}),实际最近的孔为 ({got}),偏差 {dv:.1f}mm"
                    f"(容差 ±{w.tol:g}mm;坐标原点=零件XY包围盒中心,Z 自底面向上)",
            hint="孔位必须用绝对坐标:在 cq.Workplane('XY') 上按 (x, y) 画圆柱并 .cut();"
                 "叠加台阶/凸台后 faces('>Z').workplane() 会把原点移到上层顶面中心,导致孔位整体偏移"))
    return out
