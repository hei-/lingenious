import cadquery as cq

BASE, BASE_T = 80.0, 10.0
TUBE_OD, TUBE_ID, TUBE_H = 40.0, 26.0, 35.0
FILLET_R = 3.0
HOLE_D, HOLE_EDGE = 9.0, 12.0

# feature: base plate
body = cq.Workplane("XY").box(BASE, BASE, BASE_T, centered=(True, True, False))
# feature: tube
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").circle(TUBE_OD / 2).extrude(TUBE_H)
# feature: tube root fillet
body = body.edges(cq.selectors.BoxSelector((-TUBE_OD / 2 - 1, -TUBE_OD / 2 - 1, BASE_T - 0.2), (TUBE_OD / 2 + 1, TUBE_OD / 2 + 1, BASE_T + 0.2), boundingbox=True)).fillet(FILLET_R)
# feature: axial bore
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(TUBE_ID)
# feature: corner holes
pts = [(sx * (BASE / 2 - HOLE_EDGE), sy * (BASE / 2 - HOLE_EDGE)) for sx in (-1, 1) for sy in (-1, 1)]
body = body.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints(pts).hole(HOLE_D)
result = body
