import cadquery as cq

BASE_L, BASE_W, BASE_T = 120.0, 80.0, 8.0
WALL_H, WALL_T = 60.0, 6.0
RIB_T, RIB_LEG, RIB_TIP = 5.0, 40.0, 4.0
FILLET_R = 2.0
HOLE_D, HOLE_EDGE = 9.0, 15.0

yw = -BASE_W / 2 + WALL_T      # inner face of the wall
# feature: base
base = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))
# feature: wall along the -Y long edge
wall = (cq.Workplane("XY").workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2).rect(BASE_L, WALL_T).extrude(WALL_H))
body = base.union(wall)
# feature: two triangular ribs (hypotenuse ends trimmed by a small flat tip) at both ends (flush with the end faces)
for sx in (-1, 1):
    rib = (cq.Workplane("YZ").polyline([(yw, BASE_T), (yw + RIB_LEG, BASE_T), (yw + RIB_LEG, BASE_T + RIB_TIP),
                                         (yw + RIB_TIP, BASE_T + RIB_LEG), (yw, BASE_T + RIB_LEG)]).close()
           .extrude(RIB_T).translate((BASE_L / 2 - RIB_T if sx > 0 else -BASE_L / 2, 0, 0)))
    body = body.union(rib)
# feature: inner fillets (wall/base and rib/base, rib/wall)
sel = cq.selectors.BoxSelector((-BASE_L, yw - 0.2, BASE_T - 0.2), (BASE_L, yw + 0.2, BASE_T + 0.2))
for sx in (-1, 1):
    xi = sx * (BASE_L / 2 - RIB_T)
    sel = sel + cq.selectors.BoxSelector((xi - 0.2, yw, BASE_T - 0.2), (xi + 0.2, yw + RIB_LEG, BASE_T + 0.2))
    sel = sel + cq.selectors.BoxSelector((xi - 0.2, yw - 0.2, BASE_T), (xi + 0.2, yw + 0.2, BASE_T + RIB_LEG))
    xt = sx * (BASE_L / 2 - RIB_T / 2)
    sel = sel + cq.selectors.BoxSelector((xt - 0.2, yw + RIB_LEG - 0.2, BASE_T - 0.2), (xt + 0.2, yw + RIB_LEG + 0.2, BASE_T + 0.2))
    sel = sel + cq.selectors.BoxSelector((xt - 0.2, yw - 0.2, BASE_T + RIB_LEG - 0.2), (xt + 0.2, yw + 0.2, BASE_T + RIB_LEG + 0.2))
body = body.edges(sel).fillet(FILLET_R)
# feature: corner holes
pts = [(sx * (BASE_L / 2 - HOLE_EDGE), sy * (BASE_W / 2 - HOLE_EDGE)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
