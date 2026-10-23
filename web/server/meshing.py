"""STEP -> GLB. Tessellates with CadQuery/OCC and writes a binary glTF by hand (mm units; root node rotates Z-up CAD to Y-up glTF)."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np


def _mesh(shape, tol: float, ang: float):
    """Per-face tessellation -> positions, smooth-within-face normals, indices."""
    pos, nrm, idx, base = [], [], [], 0
    for face in shape.Faces():
        verts, tris = face.tessellate(tol, ang)
        if not tris:
            continue
        v = np.array([(p.x, p.y, p.z) for p in verts], dtype=np.float32)
        t = np.array(tris, dtype=np.uint32)
        fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])  # area-weighted
        n = np.zeros_like(v)
        for k in range(3):
            np.add.at(n, t[:, k], fn)
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        pos.append(v); nrm.append(n.astype(np.float32)); idx.append(t + base)
        base += len(v)
    if not pos:
        raise ValueError("empty tessellation")
    return np.concatenate(pos), np.concatenate(nrm), np.concatenate(idx).reshape(-1)


def write_glb(shape, glb_path: Path, tol: float = 0.1, ang: float = 0.3) -> Path:
    v, n, i = _mesh(shape, tol, ang)
    vb, nb, ib = v.tobytes(), n.tobytes(), i.astype(np.uint32).tobytes()
    blob = vb + nb + ib
    gltf = {
        "asset": {"version": "2.0", "generator": "lingenious"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "part", "rotation": [-0.70710678, 0, 0, 0.70710678], "extras": {"unit": "mm"}}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": 0}]}],
        "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [0.55, 0.65, 0.8, 1], "metallicFactor": 0.4, "roughnessFactor": 0.5}}],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vb), "target": 34962},
            {"buffer": 0, "byteOffset": len(vb), "byteLength": len(nb), "target": 34962},
            {"buffer": 0, "byteOffset": len(vb) + len(nb), "byteLength": len(ib), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(v), "type": "VEC3",
             "min": v.min(0).tolist(), "max": v.max(0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": len(n), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5125, "count": len(i), "type": "SCALAR"},
        ],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    glb_path = Path(glb_path)
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    glb_path.write_bytes(b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
                         + struct.pack("<II", len(blob), 0x004E4942) + blob)
    return glb_path


def step_to_glb(step_path, glb_path, tol: float = 0.1) -> Path:
    import cadquery as cq
    shape = cq.importers.importStep(str(step_path)).val()
    return write_glb(shape, Path(glb_path), tol)
