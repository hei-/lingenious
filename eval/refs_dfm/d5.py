import cadquery as cq

# clean reading of the task text (minimal DFM fix: cavity corners R3, floor edges R2.5)
L, W, H = 100.0, 60.0, 30.0
WALL, FLOOR = 2.5, 3.0
R = 3.0
body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
tool = cq.Workplane("XY").box(L - 2 * WALL, W - 2 * WALL, H - FLOOR + 5, centered=(True, True, False))
if R > 0:
    tool = tool.edges("|Z").fillet(R)
    tool = tool.faces("<Z").edges().fillet(R - 0.5)
result = body.cut(tool.translate((0, 0, FLOOR)))
