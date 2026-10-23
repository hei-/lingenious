import cadquery as cq

L, W, T = 100.0, 70.0, 15.0
POCKET_L, POCKET_W, POCKET_D = 60.0, 30.0, 8.0
CORNER_R, FLOOR_R = 4.0, 2.0
HOLE_D, HOLE_X, HOLE_Y = 6.6, 40.0, 25.0

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: pocket (rounded tool: vertical corners and floor edges)
tool = (cq.Workplane("XY").box(POCKET_L, POCKET_W, POCKET_D + 5, centered=(True, True, False))
        .edges("|Z").fillet(CORNER_R))
tool = tool.faces("<Z").edges().fillet(FLOOR_R).translate((0, 0, T - POCKET_D))
body = body.cut(tool)
# feature: corner holes
pts = [(sx * HOLE_X, sy * HOLE_Y) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
