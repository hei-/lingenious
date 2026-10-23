import cadquery as cq

BASE_L, BASE_W, BASE_T = 100.0, 60.0, 6.0
WALL_H, WALL_T = 40.0, 3.0
FILLET_R = 3.0
HOLE_D, HOLE_EDGE = 6.6, 15.0
BIG_D = 20.0

# feature: base
base = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))
# feature: wall along the -Y long edge
wall = (cq.Workplane("XY").workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2).rect(BASE_L, WALL_T).extrude(WALL_H))
body = base.union(wall)
# feature: inner fillet
yf = -BASE_W / 2 + WALL_T
body = body.edges(cq.selectors.BoxSelector((-BASE_L, yf - 0.2, BASE_T - 0.2), (BASE_L, yf + 0.2, BASE_T + 0.2))).fillet(FILLET_R)
# feature: corner holes
pts = [(sx * (BASE_L / 2 - HOLE_EDGE), sy * (BASE_W / 2 - HOLE_EDGE)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
# feature: wall hole
cut = cq.Workplane("XZ").center(0, BASE_T + WALL_H / 2).circle(BIG_D / 2).extrude(BASE_W, both=True)
result = body.cut(cut)
