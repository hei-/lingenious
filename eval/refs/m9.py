import cadquery as cq

FLANGE_W, FLANGE_T = 80.0, 8.0
STEM_T, TOTAL_H = 8.0, 40.0
LENGTH = 60.0
FILLET_R = 3.0
HOLE_D, HOLE_X = 6.6, 28.0

# feature: T section extruded along Y
zf = TOTAL_H - FLANGE_T
h, s = FLANGE_W / 2, STEM_T / 2
prof = [(-h, TOTAL_H), (h, TOTAL_H), (h, zf), (s, zf), (s, 0), (-s, 0), (-s, zf), (-h, zf)]
body = cq.Workplane("XZ").polyline(prof).close().extrude(LENGTH / 2, both=True)
# feature: stem/flange fillets
for sx in (-1, 1):
    body = body.edges(cq.selectors.BoxSelector((sx * s - 0.2, -LENGTH, zf - 0.2), (sx * s + 0.2, LENGTH, zf + 0.2))).fillet(FILLET_R)
# feature: flange holes
cut = cq.Workplane("XY").pushPoints([(-HOLE_X, 0), (HOLE_X, 0)]).circle(HOLE_D / 2).extrude(TOTAL_H)
result = body.cut(cut)
