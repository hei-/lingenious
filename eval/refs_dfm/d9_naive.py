import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers internal_corner_radius + hole_edge_distance)
L, W, T = 80.0, 50.0, 12.0
PX, PY, PD = 40.0, 20.0, 6.0
R = 0
HX = 34.0
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
tool = cq.Workplane("XY").box(PX, PY, PD + 5, centered=(True, True, False))
if R > 0:
    tool = tool.edges("|Z").fillet(R).faces("<Z").edges().fillet(R - 0.5)
body = body.cut(tool.translate((0, 0, T - PD)))
result = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints([(-HX, 0), (HX, 0)]).hole(8.0)
