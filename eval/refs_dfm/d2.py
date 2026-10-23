import cadquery as cq

# clean reading of the task text (minimal DFM fix: both inner corners R3)
BL, BW, BT = 70.0, 40.0, 5.0
WH, WT = 25.0, 3.0
R = 3
base = cq.Workplane("XY").box(BL, BW, BT, centered=(True, True, False))
body = base
for s in (-1, 1):
    body = body.union(cq.Workplane("XY").workplane(offset=BT).center(0, s * (BW / 2 - WT / 2)).rect(BL, WT).extrude(WH))
if R > 0:
    for s in (-1, 1):
        yf = s * (BW / 2 - WT)
        body = body.edges(cq.selectors.BoxSelector((-BL, yf - 0.2, BT - 0.2), (BL, yf + 0.2, BT + 0.2))).fillet(R)
result = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints([(-20, 0), (20, 0)]).hole(6.0)
