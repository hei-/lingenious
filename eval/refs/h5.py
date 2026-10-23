import cadquery as cq

L, W = 100.0, 50.0
LOW_H, UP_H, UP_L = 10.0, 10.0, 50.0
FILLET_R = 3.0
UP_HOLE_D = 10.0
LOW_HOLE_D, LOW_HOLE_Y = 8.0, 14.0

# feature: lower tier (full length)
body = cq.Workplane("XY").box(L, W, LOW_H, centered=(True, True, False))
# feature: upper tier at the -X end
up = cq.Workplane("XY").box(UP_L, W, UP_H, centered=(False, True, False)).translate((-L / 2, 0, LOW_H))
body = body.union(up)
# feature: step root fillet
xr = -L / 2 + UP_L
body = body.edges(cq.selectors.BoxSelector((xr - 0.2, -W, LOW_H - 0.2), (xr + 0.2, W, LOW_H + 0.2))).fillet(FILLET_R)
# feature: holes (vertical, through)
cx_up = -L / 2 + UP_L / 2
cx_low = (xr + L / 2) / 2
cut = (cq.Workplane("XY").pushPoints([(cx_up, 0)]).circle(UP_HOLE_D / 2).extrude(LOW_H + UP_H)
       .union(cq.Workplane("XY").pushPoints([(cx_low, -LOW_HOLE_Y), (cx_low, LOW_HOLE_Y)])
              .circle(LOW_HOLE_D / 2).extrude(LOW_H)))
result = body.cut(cut)
