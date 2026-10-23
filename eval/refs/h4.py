import cadquery as cq

L, W, H = 80.0, 60.0, 25.0
WALL, FLOOR = 3.0, 4.0
CORNER_R, FLOOR_R = 4.0, 3.0
HOLE_D, HOLE_X, HOLE_Y = 5.5, 25.0, 15.0

# feature: outer block
body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
# feature: cavity open at the top, rounded inner corners and floor edges
tool = (cq.Workplane("XY").box(L - 2 * WALL, W - 2 * WALL, H - FLOOR + 5, centered=(True, True, False))
        .edges("|Z").fillet(CORNER_R))
tool = tool.faces("<Z").edges().fillet(FLOOR_R).translate((0, 0, FLOOR))
body = body.cut(tool)
# feature: mounting holes through the floor
pts = [(sx * HOLE_X, sy * HOLE_Y) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
