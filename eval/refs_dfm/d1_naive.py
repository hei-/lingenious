import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers internal_corner_radius)
BL, BW, BT = 80.0, 50.0, 5.0
WH, WT = 35.0, 4.0
R = 0
base = cq.Workplane("XY").box(BL, BW, BT, centered=(True, True, False))
wall = cq.Workplane("XY").workplane(offset=BT).center(0, -BW / 2 + WT / 2).rect(BL, WT).extrude(WH)
body = base.union(wall)
if R > 0:
    yf = -BW / 2 + WT
    body = body.edges(cq.selectors.BoxSelector((-BL, yf - 0.2, BT - 0.2), (BL, yf + 0.2, BT + 0.2))).fillet(R)
pts = [(-BL / 2 + 10, BW / 2 - 10), (BL / 2 - 10, BW / 2 - 10)]
result = body.cut(cq.Workplane("XY").pushPoints(pts).circle(2.5).extrude(BT))
