import cadquery as cq

L, W, T = 80.0, 50.0, 6.0
WALL_H, WALL_T = 30.0, 4.0
FILLET_R = 3.0
HOLE_D = 8.0

# feature: base
base = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
# feature: two walls along the long edges
body = base
for s in (-1, 1):
    wall = (cq.Workplane("XY").workplane(offset=T)
            .center(0, s * (W / 2 - WALL_T / 2)).rect(L, WALL_T).extrude(WALL_H))
    body = body.union(wall)
# feature: inner fillets
for s in (-1, 1):
    yf = s * (W / 2 - WALL_T)
    body = body.edges(cq.selectors.BoxSelector((-L, yf - 0.2, T - 0.2), (L, yf + 0.2, T + 0.2))).fillet(FILLET_R)
# feature: wall holes (coaxial, through both walls)
cut = cq.Workplane("XZ").center(0, T + WALL_H / 2).circle(HOLE_D / 2).extrude(W, both=True)
result = body.cut(cut)
