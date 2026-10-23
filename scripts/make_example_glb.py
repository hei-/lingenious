"""Generate part.glb (committed only if < 500KB) and thumb.png (iso-only card thumbnail) next to every examples/*/v*/part.step."""
from pathlib import Path

import cadquery as cq

from core.render import render_thumb
from web.server.meshing import step_to_glb

for step in sorted(Path("examples").glob("*/v*/part.step")):
    glb = step.with_name("part.glb")
    step_to_glb(step, glb)
    kb = glb.stat().st_size // 1024
    print(glb, f"{kb}KB")
    if kb >= 500:
        glb.unlink()
        print("  too large, removed")
    thumb = render_thumb(cq.importers.importStep(str(step)).val(), step.with_name("thumb.png"))
    print(thumb, f"{thumb.stat().st_size // 1024}KB")
