import cadquery as cq

L, W, T = 90.0, 50.0, 8.0
SLOT_L, SLOT_W = 30.0, 10.0   # overall length (ends included) and width

# feature: plate
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: slot
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").slot2D(SLOT_L, SLOT_W, 0).cutThruAll()
result = body
