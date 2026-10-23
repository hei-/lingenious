import cadquery as cq

# clean reading of the task text (minimal DFM fix: wall 1.4->1.5, inner corner R3)
BL, BW, BT = 100.0, 60.0, 8.0
WH, WT = 30.0, 1.5
R = 3
base = cq.Workplane("XY").box(BL, BW, BT, centered=(True, True, False))
wall = cq.Workplane("XY").workplane(offset=BT).center(0, -BW / 2 + WT / 2).rect(BL, WT).extrude(WH)
body = base.union(wall)
if R > 0:
    yf = -BW / 2 + WT
    body = body.edges(cq.selectors.BoxSelector((-BL, yf - 0.2, BT - 0.2), (BL, yf + 0.2, BT + 0.2))).fillet(R)
result = body
