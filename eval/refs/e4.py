import cadquery as cq

OD, T, HOLE_D = 60.0, 10.0, 12.0

# feature: disc
body = cq.Workplane("XY").circle(OD / 2).extrude(T)
# feature: center hole
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(HOLE_D)
result = body
