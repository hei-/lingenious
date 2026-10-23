import cadquery as cq

L, W, T = 100.0, 60.0, 10.0
HOLE_D, EDGE = 6.6, 15.0

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: corner holes
pts = [(sx * (L / 2 - EDGE), sy * (W / 2 - EDGE)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
