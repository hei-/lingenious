# ASSERTION_DISPUTE: thin_web_height
import cadquery as cq

# ---------------- parameters ----------------
BASE_L = 100.0          # base plate length (X)
BASE_W = 60.0           # base plate width (Y)
BASE_T = 6.0            # base plate thickness (Z)

WALL_H = 40.0           # vertical plate height above base top
WALL_T = 4.0            # vertical plate thickness (Y)

CORNER_HOLE_D = 6.6     # M6 clearance hole diameter
CORNER_HOLE_X = 36.8    # corner hole |x| position
CORNER_HOLE_Y = 16.8    # corner hole |y| position

WALL_HOLE_D = 20.0      # vertical plate hole diameter
WALL_HOLE_Z = 26.0      # hole centre height (from base bottom)

INNER_FILLET_R = 3.0    # inner corner fillet radius (base top / wall)

# ---------------- feature: base ----------------
body = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))

# ---------------- feature: vertical_plate ----------------
# wall sits along the -Y long edge, outer face flush with base edge
wall = (cq.Workplane("XY").workplane(offset=BASE_T)
        .center(0, -BASE_W / 2 + WALL_T / 2)
        .rect(BASE_L, WALL_T)
        .extrude(WALL_H))
body = body.union(wall)

# ---------------- feature: inner_fillet (base top / wall junction) ----------------
# fillet the concave inner edge where the wall meets the base top face
body = body.edges(cq.selectors.BoxSelector(
    (-BASE_L / 2 - 1.0, -BASE_W / 2 + WALL_T - 0.1, BASE_T - 0.1),
    (BASE_L / 2 + 1.0, -BASE_W / 2 + WALL_T + 0.1, BASE_T + 0.1))).fillet(INNER_FILLET_R)

# ---------------- feature: corner holes (M6, through base) ----------------
corner_pts = [(sx * CORNER_HOLE_X, sy * CORNER_HOLE_Y)
              for sx in (-1, 1) for sy in (-1, 1)]
body = body.cut(cq.Workplane("XY").pushPoints(corner_pts)
                .circle(CORNER_HOLE_D / 2).extrude(BASE_T))

# ---------------- feature: vertical_hole (D20, through wall along Y) ----------------
# cylinder axis along Y, centred at x=0, z=WALL_HOLE_Z, spanning full wall thickness
# build on XY plane, extrude along Y using a rotated workplane with explicit origin
hole = (cq.Workplane("XY")
        .workplane(origin=(0, 0, 0))
        .center(0, 0)
        .transformed(offset=(0, 0, 0), rotate=(90, 0, 0))
        .center(0, WALL_HOLE_Z)
        .circle(WALL_HOLE_D / 2)
        .extrude(BASE_W + 2.0))
body = body.cut(hole)

result = body