import cadquery as cq

OD, T = 100.0, 10.0
BORE_D = 30.0
PCD, N, HOLE_D = 70.0, 6, 9.0

# feature: disc
body = cq.Workplane("XY").circle(OD / 2).extrude(T)
# feature: center bore
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(BORE_D)
# feature: bolt circle
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").polarArray(PCD / 2, 0, 360, N).hole(HOLE_D)
result = body
