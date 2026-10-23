import cadquery as cq

# clean reading of the task text (minimal DFM fix: inner corner R3; hole centre lowered by 3 mm (9 mm below top edge))
BL, BW, BT = 90.0, 50.0, 6.0
WT = 3.0
WH = 30.0
HZ = 24.0
R = 3
base = cq.Workplane("XY").box(BL, BW, BT, centered=(True, True, False))
wall = cq.Workplane("XY").workplane(offset=BT).center(0, -BW / 2 + WT / 2).rect(BL, WT).extrude(WH)
body = base.union(wall)
if R > 0:
    yf = -BW / 2 + WT
    body = body.edges(cq.selectors.BoxSelector((-BL, yf - 0.2, BT - 0.2), (BL, yf + 0.2, BT + 0.2))).fillet(R)
cut = cq.Workplane("XZ").center(0, 27.0).circle(3.0).extrude(BW, both=True)
result = body.cut(cut)
