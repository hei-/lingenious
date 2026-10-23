import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers hole_spacing)
L, W, T = 120.0, 50.0, 10.0
P = 14.0
result = cq.Workplane("XY").box(L, W, T).faces(">Z").workplane().pushPoints([(-P, 0), (0, 0), (P, 0)]).hole(10.0)
