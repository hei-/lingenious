import cadquery as cq

# clean reading of the task text (minimal DFM fix: pitch 20.5 mm)
L, W, T = 120.0, 50.0, 10.0
P = 20.5
result = cq.Workplane("XY").box(L, W, T).faces(">Z").workplane().pushPoints([(-P, 0), (0, 0), (P, 0)]).hole(10.0)
