import cadquery as cq

L, W, H = 100.0, 60.0, 30.0
WALL, FLOOR = 3.0, 3.0
INNER_R = 3.0

# feature: outer block
body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
# feature: cavity (rounded tool: vertical corners and floor edges), open at the top
tool = (cq.Workplane("XY").box(L - 2 * WALL, W - 2 * WALL, H - FLOOR + 5, centered=(True, True, False))
        .edges("|Z").fillet(INNER_R))
tool = tool.faces("<Z").edges().fillet(INNER_R - 0.5).translate((0, 0, FLOOR))
result = body.cut(tool)
