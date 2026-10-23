import cadquery as cq

# ---------------- parameters ----------------
PLATE_L = 120.0          # length along X
PLATE_W = 80.0           # width along Y
PLATE_T = 8.0            # thickness along Z

CORNER_HOLE_D = 9.0      # M8 clearance through hole
CORNER_HOLE_X = 42.0     # absolute X of corner holes
CORNER_HOLE_Y = 22.0     # absolute Y of corner holes

CENTER_HOLE_D = 30.0     # central through hole

CHAMFER_R = 3.0          # edge chamfer (45 deg, R3)

# ---------------- feature: base ----------------
body = cq.Workplane("XY").box(PLATE_L, PLATE_W, PLATE_T, centered=(True, True, False))

# ---------------- feature: F3 chamfer (four vertical corner edges) ----------------
body = body.edges("|Z").chamfer(CHAMFER_R)

# ---------------- feature: F1 corner through holes ----------------
corner_pts = [
    (-CORNER_HOLE_X, -CORNER_HOLE_Y),
    ( CORNER_HOLE_X, -CORNER_HOLE_Y),
    (-CORNER_HOLE_X,  CORNER_HOLE_Y),
    ( CORNER_HOLE_X,  CORNER_HOLE_Y),
]
body = body.cut(
    cq.Workplane("XY").pushPoints(corner_pts)
    .circle(CORNER_HOLE_D / 2).extrude(PLATE_T)
)

# ---------------- feature: F2 central through hole ----------------
body = body.cut(
    cq.Workplane("XY").pushPoints([(0.0, 0.0)])
    .circle(CENTER_HOLE_D / 2).extrude(PLATE_T)
)

result = body