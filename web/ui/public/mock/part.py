import cadquery as cq

# ---------------- parameters ----------------
BASE_L = 100.0          # base plate length (X)
BASE_W = 60.0           # base plate width (Y)
BASE_T = 6.0            # base plate thickness (Z)

WALL_H = 40.0           # vertical plate height above base top
WALL_T = 3.0            # vertical plate thickness (Y)
WALL_L = 100.0          # vertical plate length (X)

HOLE_D = 6.6            # M6 clearance hole diameter
HOLE_EDGE = 12.0        # corner hole offset from both edges

BIG_HOLE_D = 20.0       # vertical plate center hole diameter
BIG_HOLE_Z = BASE_T + WALL_H / 2.0   # centered along wall height

FILLET_R = 3.0          # inner corner fillet radius (base top / wall)

# ---------------- feature: base_plate ----------------
body = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))

# ---------------- feature: vertical_plate ----------------
# wall sits along the -Y long edge, rising from base top
wall = (cq.Workplane("XY")
        .workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2)
        .rect(WALL_L, WALL_T)
        .extrude(WALL_H))
body = body.union(wall)

# ---------------- feature: inner_fillet (base top / wall junction) ----------------
body = body.edges(cq.selectors.BoxSelector(
    (-BASE_L, -BASE_W / 2 + WALL_T - 0.1, BASE_T - 0.1),
    (BASE_L, -BASE_W / 2 + WALL_T + 0.1, BASE_T + 0.1))).fillet(FILLET_R)

# ---------------- feature: hole1..hole4 (corner M6 through holes) ----------------
pts = [(sx * (BASE_L / 2 - HOLE_EDGE), sy * (BASE_W / 2 - HOLE_EDGE))
       for sx in (-1, 1) for sy in (-1, 1)]
body = (body.faces("<Z")
        .workplane(centerOption="CenterOfBoundBox")
        .pushPoints(pts)
        .hole(HOLE_D))

# ---------------- feature: hole5 (vertical plate center hole) ----------------
# cut through the wall thickness along Y
body = (body.faces(">Y")
        .workplane(centerOption="CenterOfBoundBox")
        .center(0, BIG_HOLE_Z - BASE_T - WALL_H / 2 + WALL_H / 2)
        .pushPoints([(0, 0)])
        .hole(BIG_HOLE_D))

result = body