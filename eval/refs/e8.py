import cadquery as cq

L, W, T = 50.0, 30.0, 12.0
CHAMFER = 2.0

# feature: block
body = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: top edge chamfer
body = body.faces(">Z").edges().chamfer(CHAMFER)
result = body
