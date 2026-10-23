import cadquery as cq

L, W, T = 100.0, 70.0, 8.0
HOLE_D, PITCH_X, PITCH_Y = 6.0, 30.0, 30.0
NX, NY = 3, 2

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: hole grid
pts = [((i - (NX - 1) / 2) * PITCH_X, (j - (NY - 1) / 2) * PITCH_Y) for i in range(NX) for j in range(NY)]
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
