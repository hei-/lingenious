import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers hole_edge_distance)
L, W, T = 60.0, 40.0, 6.0
E = 6.0
pts = [(sx * (L / 2 - E), sy * (W / 2 - E)) for sx in (-1, 1) for sy in (-1, 1)]
result = cq.Workplane("XY").box(L, W, T).faces(">Z").workplane().pushPoints(pts).hole(6.0)
