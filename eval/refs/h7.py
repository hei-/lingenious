import cadquery as cq

BASE_L, BASE_W, BASE_T = 100.0, 60.0, 8.0
WALL_H, WALL_T = 40.0, 5.0
FILLET_R = 3.0
SLOT_L, SLOT_W, SLOT_Y = 40.0, 8.0, 8.0
HOLE_D, HOLE_X = 6.0, 25.0

# feature: base
base = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))
# feature: wall along the -Y long edge
wall = (cq.Workplane("XY").workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2).rect(BASE_L, WALL_T).extrude(WALL_H))
body = base.union(wall)
# feature: inner fillet
yf = -BASE_W / 2 + WALL_T
body = body.edges(cq.selectors.BoxSelector((-BASE_L, yf - 0.2, BASE_T - 0.2), (BASE_L, yf + 0.2, BASE_T + 0.2))).fillet(FILLET_R)
# feature: slot in the base
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").center(0, -SLOT_Y).slot2D(SLOT_L, SLOT_W, 0).cutThruAll()
# feature: wall holes
cut = (cq.Workplane("XZ").pushPoints([(-HOLE_X, BASE_T + WALL_H / 2), (HOLE_X, BASE_T + WALL_H / 2)])
       .circle(HOLE_D / 2).extrude(BASE_W, both=True))
result = body.cut(cut)
