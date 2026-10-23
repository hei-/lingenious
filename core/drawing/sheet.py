"""Backend-neutral 2D sheet (lines/polylines/text) with DXF (ezdxf) and PDF/PNG (matplotlib) writers.

Both writers consume the same primitive list so the DXF and PDF always agree.
Units: sheet millimetres.
"""
from __future__ import annotations

from pathlib import Path

LAYERS = {
    # name: (aci color, linetype, lineweight 1/100 mm, mpl color, mpl lw (pt), mpl dashes)
    "VISIBLE": (7, "CONTINUOUS", 50, "black", 1.3, None),
    "HIDDEN": (1, "DASHED", 25, "#444444", 0.7, (4, 2)),
    "CENTER": (5, "CENTER", 18, "#1f4e9c", 0.5, (8, 1.5, 1.5, 1.5)),
    "DIM": (3, "CONTINUOUS", 18, "#0a7a2f", 0.5, None),
    "TEXT": (7, "CONTINUOUS", 25, "black", 0.8, None),
    "HATCH": (8, "CONTINUOUS", 13, "#555555", 0.35, None),
    "FRAME": (7, "CONTINUOUS", 35, "black", 1.0, None),
}
_ALIGN = {"L": "left", "C": "center", "R": "right"}


class Sheet:
    def __init__(self, width: float = 420.0, height: float = 297.0):
        self.w, self.h = width, height
        self.polys: list[tuple[str, list]] = []
        self.texts: list[tuple[str, float, float, str, float, float, str]] = []
        self.circles: list[tuple[str, float, float, float]] = []

    # -- primitives
    def line(self, layer, p1, p2):
        self.polys.append((layer, [tuple(p1), tuple(p2)]))

    def poly(self, layer, pts, closed=False):
        pts = [tuple(p) for p in pts]
        if closed:
            pts = pts + [pts[0]]
        if len(pts) >= 2:
            self.polys.append((layer, pts))

    def rect(self, layer, x1, y1, x2, y2):
        self.poly(layer, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], closed=True)

    def circle(self, layer, cx, cy, r):
        self.circles.append((layer, cx, cy, r))

    def text(self, layer, x, y, s, h=3.0, rot=0.0, align="L"):
        self.texts.append((layer, x, y, str(s), h, rot, align))

    # -- DXF
    def write_dxf(self, path: Path):
        import ezdxf
        from ezdxf.enums import TextEntityAlignment

        doc = ezdxf.new("R2010", setup=True)
        doc.units = 4  # mm
        for name, (aci, lt, lw, *_rest) in LAYERS.items():
            if name not in doc.layers:
                doc.layers.add(name)
            L = doc.layers.get(name)
            L.color = aci
            L.dxf.linetype = lt if lt in doc.linetypes else "CONTINUOUS"
            L.dxf.lineweight = lw
        doc.header["$LTSCALE"] = 1.0
        msp = doc.modelspace()
        for layer, pts in self.polys:
            if len(pts) == 2:
                msp.add_line(pts[0], pts[1], dxfattribs={"layer": layer})
            else:
                msp.add_lwpolyline(pts, dxfattribs={"layer": layer})
        for layer, cx, cy, r in self.circles:
            msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})
        al = {"L": TextEntityAlignment.LEFT, "C": TextEntityAlignment.CENTER, "R": TextEntityAlignment.RIGHT}
        for layer, x, y, s, h, rot, a in self.texts:
            t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer})
            t.set_placement((x, y), align=al[a])
        doc.saveas(str(path))

    # -- PDF / PNG
    def write_pdf(self, pdf_path: Path, png_path: Path | None = None):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle

        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig = plt.figure(figsize=(self.w / 25.4, self.h / 25.4))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, self.w)
        ax.set_ylim(0, self.h)
        ax.axis("off")
        for layer, pts in self.polys:
            _, _, _, col, lw, dash = LAYERS[layer]
            xs, ys = zip(*pts)
            ln, = ax.plot(xs, ys, color=col, lw=lw, solid_capstyle="butt", solid_joinstyle="round")
            if dash:
                ln.set_dashes(dash)
        for layer, cx, cy, r in self.circles:
            col, lw = LAYERS[layer][3], LAYERS[layer][4]
            ax.add_patch(Circle((cx, cy), r, fill=False, ec=col, lw=lw))
        for layer, x, y, s, h, rot, a in self.texts:
            s = s.replace("⌴", "⊔")  # U+2334 is missing from common fonts; U+2294 is its look-alike
            ax.text(x, y, s, fontsize=h * 72 / 25.4 * 0.8, rotation=rot, rotation_mode="anchor",
                    ha=_ALIGN[a], va="baseline", color=LAYERS[layer][3])
        fig.savefig(str(pdf_path), format="pdf")
        if png_path:
            fig.savefig(str(png_path), format="png", dpi=130)
        plt.close(fig)
