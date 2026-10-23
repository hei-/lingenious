import cadquery as cq

# naive reading of the task text (literal, no DFM fixes; triggers min_wall_thickness + internal_corner_radius)
L, W, T = 80.0, 50.0, 6.0
RL, RT, RH = 80.0, 1.2, 20.0
R = 0
base = cq.Workplane("XY").box(L, W, T, centered=(True, True, False))
rib = cq.Workplane("XY").workplane(offset=T).rect(RL, RT).extrude(RH)
body = base.union(rib)
if R > 0:
    for s in (-1, 1):
        body = body.edges(cq.selectors.BoxSelector((-RL, s * RT / 2 - 0.2, T - 0.2), (RL, s * RT / 2 + 0.2, T + 0.2))).fillet(R)
result = body
