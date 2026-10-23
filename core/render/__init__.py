"""Software renderer (matplotlib 2D, painter's algorithm): isometric + 3 orthographic views of a tessellated B-Rep.
No GL needed, so it runs in a plain container."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.collections import PolyCollection

for _f in ("WenQuanYi Micro Hei", "Noto Sans CJK SC", "PingFang SC", "Heiti SC"):
    if any(_f == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f]
        plt.rcParams["axes.unicode_minus"] = False
        break

LIGHT = np.array([0.35, -0.45, 0.82])
LIGHT /= np.linalg.norm(LIGHT)
VIEWS = [("等轴测", 28, -50), ("俯视", 90, -90), ("正视", 0, -90), ("右视", 0, 0)]


def _mesh(shape, tol: float = 0.15):
    verts, tris = shape.tessellate(tol)
    v = np.array([(p.x, p.y, p.z) for p in verts])
    return v, np.array(tris)


def _shaded(shape):
    v, t = _mesh(shape)
    tri = v[t]                                           # (n, 3, 3)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    shade = 0.3 + 0.7 * np.abs(nrm @ LIGHT)
    colors = np.stack([shade * 0.50, shade * 0.68, shade * 0.92, np.ones_like(shade)], axis=1)
    return tri, colors


def _draw_view(ax, tri, colors, elev: float, azim: float, pad_frac: float = 0.08, cull: bool = False) -> None:
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    if cull:  # drop back faces (closed solid, outward-oriented triangles): removes most painter's-order artifacts
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        keep = nrm @ d > 0
        if keep.any():
            tri, colors = tri[keep], colors[keep]
    right = np.array([-np.sin(a), np.cos(a), 0.0])
    up = np.array([-np.sin(e) * np.cos(a), -np.sin(e) * np.sin(a), np.cos(e)])
    pts2 = np.stack([tri @ right, tri @ up], axis=-1)           # (n, 3, 2)
    order = np.argsort((tri @ d).mean(axis=1))                   # far -> near
    ax.add_collection(PolyCollection(list(pts2[order]), facecolors=colors[order],
                                     edgecolors=colors[order], linewidths=0.3))
    lo, hi = pts2.reshape(-1, 2).min(0), pts2.reshape(-1, 2).max(0)
    pad = max((hi - lo).max() * pad_frac, 1)
    ax.set_xlim(lo[0] - pad, hi[0] + pad); ax.set_ylim(lo[1] - pad, hi[1] + pad)
    ax.set_aspect("equal"); ax.set_axis_off()


def render_thumb(shape, path: Path, width_px: int = 480) -> Path:
    """Isometric view only, transparent background, no titles (card thumbnails). render.png is unchanged.
    Uses a small numpy z-buffer (2x supersampled) instead of the painter's algorithm, so no ordering artifacts."""
    tri, colors = _shaded(shape)
    _, elev, azim = VIEWS[0]
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.array([-np.sin(a), np.cos(a), 0.0])
    up = np.array([-np.sin(e) * np.cos(a), -np.sin(e) * np.sin(a), np.cos(e)])
    ss = 2
    W, H = width_px * ss, int(width_px * 0.75) * ss
    x, y, z = tri @ right, tri @ up, tri @ d                      # (n, 3) each; larger z = nearer
    lo, hi = np.array([x.min(), y.min()]), np.array([x.max(), y.max()])
    scale = 0.92 * min(W / max(hi[0] - lo[0], 1e-9), H / max(hi[1] - lo[1], 1e-9))
    px = (x - (lo[0] + hi[0]) / 2) * scale + W / 2
    py = H / 2 - (y - (lo[1] + hi[1]) / 2) * scale
    zbuf = np.full((H, W), -np.inf)
    img = np.zeros((H, W, 4))
    for i in range(len(tri)):
        x0, x1 = int(max(np.floor(px[i].min()), 0)), int(min(np.ceil(px[i].max()), W - 1))
        y0, y1 = int(max(np.floor(py[i].min()), 0)), int(min(np.ceil(py[i].max()), H - 1))
        if x1 < x0 or y1 < y0:
            continue
        (ax_, bx, cx), (ay, by, cy) = px[i], py[i]
        den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax_ - cx) * (gy - cy)) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        depth = w0 * z[i, 0] + w1 * z[i, 1] + w2 * z[i, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        win = inside & (depth > sub)
        sub[win] = depth[win]
        img[y0:y1 + 1, x0:x1 + 1][win] = colors[i]
    img = img.reshape(H // ss, ss, W // ss, ss, 4).mean(axis=(1, 3))  # downsample (antialias)
    path = Path(path)
    plt.imsave(path, np.clip(img, 0, 1))
    return path


def render(shape, path: Path, title: str = "") -> Path:
    tri, colors = _shaded(shape)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (name, elev, azim) in zip(axes.ravel(), VIEWS):
        _draw_view(ax, tri, colors, elev, azim)
        ax.set_title(name, fontsize=10)
    if title:
        fig.suptitle(title, fontsize=11)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.92, wspace=0.05, hspace=0.12)
    path = Path(path)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
