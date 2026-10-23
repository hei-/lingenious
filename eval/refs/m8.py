import cadquery as cq

L, W, H = 80.0, 50.0, 25.0
HOLE_D, DEPTH = 8.0, 15.0
PITCH_X, PITCH_Y = 50.0, 25.0

# feature: block
body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
# feature: blind holes from the top face
pts = [(sx * PITCH_X / 2, sy * PITCH_Y / 2) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D, DEPTH)
result = body
