import cadquery as cq

OD, T = 120.0, 12.0
BORE_D = 40.0
PCD, N = 90.0, 8
HOLE_D, CB_D, CB_DEPTH = 9.0, 15.0, 6.0

# feature: disc
body = cq.Workplane("XY").circle(OD / 2).extrude(T)
# feature: center bore
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(BORE_D)
# feature: counterbored bolt holes from the +Z face
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").polarArray(PCD / 2, 0, 360, N).cboreHole(HOLE_D, CB_D, CB_DEPTH)
result = body
