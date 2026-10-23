import cadquery as cq

L, W, T = 120.0, 40.0, 5.0
HOLE_D, PITCH, N = 8.0, 30.0, 3

# feature: strip
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: holes along length
pts = [((i - (N - 1) / 2) * PITCH, 0) for i in range(N)]
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
