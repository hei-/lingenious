import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers min_wall_thickness + internal_corner_radius)
BL, BW, BT = 100.0, 60.0, 8.0
WH, WT = 30.0, 1.4
R = 0
base = cq.Workplane("XY").box(BL, BW, BT, centered=(True, True, False))
wall = cq.Workplane("XY").workplane(offset=BT).center(0, -BW / 2 + WT / 2).rect(BL, WT).extrude(WH)
body = base.union(wall)
if R > 0:
    yf = -BW / 2 + WT
    body = body.edges(cq.selectors.BoxSelector((-BL, yf - 0.2, BT - 0.2), (BL, yf + 0.2, BT + 0.2))).fillet(R)
result = body
