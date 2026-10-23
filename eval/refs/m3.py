import cadquery as cq

L, W, H = 60.0, 40.0, 20.0
STEP_L, STEP_H = 20.0, 10.0
FILLET_R = 3.0

# feature: block
body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
# feature: step at the +X end
cutter = (cq.Workplane("XY").box(STEP_L, W, STEP_H, centered=(False, True, False))
          .translate((L / 2 - STEP_L, 0, H - STEP_H)))
body = body.cut(cutter)
# feature: step root fillet
xr = L / 2 - STEP_L
body = body.edges(cq.selectors.BoxSelector((xr - 0.2, -W, H - STEP_H - 0.2), (xr + 0.2, W, H - STEP_H + 0.2))).fillet(FILLET_R)
result = body
