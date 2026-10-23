import cadquery as cq
import math

ACROSS_FLATS, H = 30.0, 15.0     # flats face +-Y; corners lie on the X axis
HOLE_D = 10.0

# feature: hex prism
body = cq.Workplane("XY").polygon(6, ACROSS_FLATS / math.cos(math.radians(30))).extrude(H)
# feature: center hole
body = body.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(HOLE_D)
result = body
