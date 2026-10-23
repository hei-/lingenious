import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers internal_corner_radius + hole_edge_distance)
L, W = 80.0, 50.0
R = 0
HX = 34.0
low = cq.Workplane("XY").box(L, W, 10.0, centered=(True, True, False))
up = cq.Workplane("XY").workplane(offset=10.0).center(-20.0, 0).rect(40.0, W).extrude(10.0)
body = low.union(up)
if R > 0:
    body = body.edges(cq.selectors.BoxSelector((-1, -W, 9.8), (1, W, 10.2))).fillet(R)
holes = cq.Workplane("XY").pushPoints([(-20.0, 0), (HX, 0)]).circle(4.0).extrude(30.0)
result = body.cut(holes)
