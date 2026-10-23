#!/usr/bin/env python3
"""Build the data files of the landing page (web/landing/data/) from the real run in examples/bracket/v1.

  replay.json        run.json (+ part.py, log.txt); every round's script as saved by the run
  part_r<n>.glb      geometry of each non-final round, part.glb for the final one (needs cadquery)

examples/bracket is produced by scripts/make_examples.py (genuine agent run, unedited).

usage (inside the container, repo at /app):
    python scripts/export_landing_data.py [--root .] [--out web/landing/data]
replay.json needs no cadquery; GLB export is skipped when cadquery is missing.
"""
import argparse
import json
import struct
import sys
from pathlib import Path


def build_replay(root: Path):
    v1 = root / "examples/bracket/v1"
    run = json.loads((v1 / "run.json").read_text(encoding="utf-8"))
    final_code = (v1 / "part.py").read_text(encoding="utf-8")
    spec = run["spec"]
    rounds = []
    for r in run["rounds"]:
        issues = []
        for i in r["issues"]:
            it = {k: i.get(k) for k in ("rule", "level", "severity", "target", "message", "measured", "required", "hint")}
            if i.get("location"):
                it["location"] = i["location"]
            issues.append(it)
        rounds.append({"n": r["n"], "seconds": r["seconds"], "issues": issues, "code": r["code"],
                       "code_reconstructed": False, "model": f"part_r{r['n']}.glb"})
    rounds[-1]["model"] = "part.glb"
    assert rounds[-1]["code"].strip() == final_code.strip()
    # checks that ran, for the pass/fail grid (rule ids from docs/dfm-rules.md relevant to this part)
    checked = ["valid_solid", "single_solid", "positive_volume", "bbox_match", "hole_count",
              "hole_diameter", "hole_position", "min_wall_thickness", "hole_edge_distance",
              "internal_corner_radius", "hole_spacing", "hole_depth_ratio", "deep_pocket", "thin_web_height"]
    return {
        "requirement": json.loads((root / "examples/bracket/meta.json").read_text(encoding="utf-8"))["request"],
        "material": "6061",
        "status": run["status"],
        "spec": {
            "part_type": spec["part_type"],
            "features": [{"id": f["id"], "type": f["type"], "dims": f["dims"]} for f in spec["features"]],
            "assertions": spec["assertions"],
            "defaults_used": spec["defaults_used"],
        },
        "rounds": rounds,
        "checked_rules": checked,
        "usage": run["usage"],
        "final_issues": run["final_issues"],
        "log": (v1 / "log.txt").read_text(encoding="utf-8").strip().splitlines(),
    }


# ---------------------------------------------------------------- GLB
def to_y_up(p):
    x, y, z = p
    return (x, z, -y)


def shape_to_glb(shape, path: Path, tol=0.1):
    import numpy as np
    tris, normals = [], []
    for face in shape.Faces():
        vs, ts = face.tessellate(tol, 0.3)
        for a, b, c in ts:
            p = [np.array(to_y_up((vs[i].x, vs[i].y, vs[i].z)), dtype="f4") for i in (a, b, c)]
            n = np.cross(p[1] - p[0], p[2] - p[0])
            l = np.linalg.norm(n)
            if l < 1e-12:
                continue
            n = (n / l).astype("f4")
            tris.extend(p)
            normals.extend([n] * 3)
    segs = []
    for e in shape.Edges():
        n = 1 if e.geomType() == "LINE" else 48
        pts = [e.positionAt(i / n) for i in range(n + 1)]
        pts = [to_y_up((q.x, q.y, q.z)) for q in pts]
        for a, b in zip(pts, pts[1:]):
            segs.extend([a, b])
    P = np.array(tris, dtype="f4").reshape(-1, 3)
    N = np.array(normals, dtype="f4").reshape(-1, 3)
    L = np.array(segs, dtype="f4").reshape(-1, 3)
    blobs = [P.tobytes(), N.tobytes(), L.tobytes()]
    views, off = [], 0
    for b in blobs:
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b), "target": 34962})
        off += len(b)

    def acc(i, arr):
        return {"bufferView": i, "componentType": 5126, "count": len(arr), "type": "VEC3",
                "min": arr.min(0).tolist(), "max": arr.max(0).tolist()}

    gltf = {
        "asset": {"version": "2.0", "generator": "lingenious export_landing_data.py"},
        "scene": 0, "scenes": [{"nodes": [0, 1]}],
        "nodes": [{"mesh": 0, "name": "solid"}, {"mesh": 1, "name": "edges"}],
        "meshes": [
            {"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "mode": 4}]},
            {"primitives": [{"attributes": {"POSITION": 2}, "mode": 1}]},
        ],
        "accessors": [acc(0, P), acc(1, N), acc(2, L)],
        "bufferViews": views,
        "buffers": [{"byteLength": off}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_ = b"".join(blobs)
    bin_ += b"\0" * (-len(bin_) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total)
                     + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(bin_), 0x004E4942) + bin_)
    print(f"wrote {path} ({path.stat().st_size} bytes, {len(P)//3} triangles, {len(L)//2} edge segments)")


def run_script(code: str):
    ns = {}
    exec(compile(code, "part.py", "exec"), ns)
    res = ns["result"]
    return res.val() if hasattr(res, "val") else res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="web/landing/data")
    a = ap.parse_args()
    root, out = Path(a.root).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    final_code = (root / "examples/bracket/v1/part.py").read_text(encoding="utf-8")
    replay = build_replay(root)
    try:
        import cadquery  # noqa: F401
    except ImportError:
        print("cadquery missing: skipping GLB (run inside the docker image)", file=sys.stderr)
    else:
        for r in replay["rounds"]:
            shape_to_glb(run_script(r["code"]), out / r["model"])
        bb = run_script(final_code).BoundingBox()
        replay["bbox"] = [round(v, 3) for v in (bb.xlen, bb.ylen, bb.zlen)]
    (out / "replay.json").write_text(json.dumps(replay, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out / "replay.json")


if __name__ == "__main__":
    main()
