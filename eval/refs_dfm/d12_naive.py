import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers internal_corner_radius + hole_edge_distance)
S, BT = 70.0, 8.0
E = 6.0
R = 0
base = cq.Workplane("XY").box(S, S, BT, centered=(True, True, False))
tube = cq.Workplane("XY").workplane(offset=BT).circle(18.0).extrude(30.0)
body = base.union(tube)
if R > 0:
    body = body.edges(cq.selectors.BoxSelector((-20, -20, BT - 0.2), (20, 20, BT + 0.2))).fillet(R)
pts = [(sx * (S / 2 - E), sy * (S / 2 - E)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.cut(cq.Workplane("XY").circle(11.0).extrude(BT + 30.0))
result = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(8.0)
