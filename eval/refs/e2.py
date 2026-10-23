import cadquery as cq

L, W, T = 80.0, 80.0, 8.0
HOLE_D = 20.0

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: center hole
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(HOLE_D)
result = body
