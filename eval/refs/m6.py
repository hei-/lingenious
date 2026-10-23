import cadquery as cq

D1, H1 = 40.0, 20.0
D2, H2 = 25.0, 30.0
HOLE_D = 10.0
FILLET_R = 2.0

# feature: lower cylinder
body = cq.Workplane("XY").circle(D1 / 2).extrude(H1)
# feature: upper cylinder
body = body.faces(">Z").workplane().circle(D2 / 2).extrude(H2)
# feature: step root fillet
body = body.edges(cq.selectors.BoxSelector((-D2 / 2 - 1, -D2 / 2 - 1, H1 - 0.2), (D2 / 2 + 1, D2 / 2 + 1, H1 + 0.2), boundingbox=True)).fillet(FILLET_R)
# feature: axial through hole
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(HOLE_D)
result = body
