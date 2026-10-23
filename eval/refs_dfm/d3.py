import cadquery as cq

# clean reading of the task text (minimal DFM fix: holes moved to 9 mm from edges)
L, W, T = 60.0, 40.0, 6.0
E = 9.0
pts = [(sx * (L / 2 - E), sy * (W / 2 - E)) for sx in (-1, 1) for sy in (-1, 1)]
result = cq.Workplane("XY").box(L, W, T).faces(">Z").workplane().pushPoints(pts).hole(6.0)
