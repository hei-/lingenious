import cadquery as cq

L, W, T = 80.0, 40.0, 10.0
BIG_D, SMALL_D, OFFSET = 16.0, 8.0, 20.0   # hole centers at +-OFFSET from the middle

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: big hole (-X side) and small hole (+X side)
wp = body.faces(">Z").workplane(centerOption="CenterOfBoundBox")
body = wp.center(-OFFSET, 0).hole(BIG_D)
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").center(OFFSET, 0).hole(SMALL_D)
result = body
