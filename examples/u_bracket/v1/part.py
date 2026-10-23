import cadquery as cq

# ---------------- parameters ----------------
BASE_L = 80.0          # length along X
BASE_W = 50.0          # width along Y
BASE_T = 4.0           # base plate thickness

WALL_H = 35.0          # total height including base
WALL_T = 4.0           # side wall thickness

HOLE_D = 8.0           # side wall hole diameter
HOLE_X = 0.0           # hole x position (centered along length)
HOLE_Z = 17.5          # hole z position (centered on wall height)

INNER_FILLET_R = 3.0   # inner corner fillet radius (base-to-wall)

# ---------------- feature: base ----------------
body = cq.Workplane("XY").box(BASE_L, BASE_W, BASE_T, centered=(True, True, False))

# ---------------- feature: side wall 1 (F2) ----------------
wall1 = (cq.Workplane("XY").workplane(offset=0)
         .center(0, -BASE_W / 2 + WALL_T / 2)
         .rect(BASE_L, WALL_T)
         .extrude(WALL_H))
body = body.union(wall1)

# ---------------- feature: side wall 2 (F3) ----------------
wall2 = (cq.Workplane("XY").workplane(offset=0)
         .center(0, BASE_W / 2 - WALL_T / 2)
         .rect(BASE_L, WALL_T)
         .extrude(WALL_H))
body = body.union(wall2)

# ---------------- feature: inner fillets (base-to-wall inner corners) ----------------
body = body.edges(cq.selectors.BoxSelector(
    (-BASE_L, -BASE_W / 2 + WALL_T - 0.1, BASE_T - 0.1),
    (BASE_L, -BASE_W / 2 + WALL_T + 0.1, BASE_T + 0.1))).fillet(INNER_FILLET_R)
body = body.edges(cq.selectors.BoxSelector(
    (-BASE_L, BASE_W / 2 - WALL_T - 0.1, BASE_T - 0.1),
    (BASE_L, BASE_W / 2 - WALL_T + 0.1, BASE_T + 0.1))).fillet(INNER_FILLET_R)

# ---------------- feature: H1 (hole through wall 1, axis Y) ----------------
h1 = (cq.Workplane("XZ").workplane(offset=-(BASE_W / 2))
      .center(HOLE_X, HOLE_Z)
      .circle(HOLE_D / 2)
      .extrude(BASE_W))
body = body.cut(h1)

# ---------------- feature: H2 (hole through wall 2, axis Y) ----------------
h2 = (cq.Workplane("XZ").workplane(offset=-(BASE_W / 2))
      .center(HOLE_X, HOLE_Z)
      .circle(HOLE_D / 2)
      .extrude(BASE_W))
body = body.cut(h2)

result = body