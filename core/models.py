"""Shared data contracts: PartSpec (input of checks) and Issue (output of checks)."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    x: float
    y: float
    z: float
    tol: float = 0.5


class HolePos(BaseModel):
    """Expected hole axis position. Coordinates use the shared convention: origin at the centre of the part's
    XY bounding box, Z measured up from the bbox bottom (z=0). Checked relative to the actual bbox, so the
    script's own origin does not matter. Unknown coordinates are None (not checked); the coordinate along the
    hole axis is ignored."""
    diameter: float
    axis: Literal["X", "Y", "Z"] = "Z"
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    tol: float = 1.0


class Assertions(BaseModel):
    bbox: Optional[BBox] = None
    hole_count: Optional[int] = None
    hole_diameters: list[float] = Field(default_factory=list)  # multiset, mm
    diameter_tol: float = 0.1
    volume_range: Optional[tuple[Optional[float], Optional[float]]] = None
    hole_positions: list[HolePos] = Field(default_factory=list)


class Feature(BaseModel):
    id: str
    type: str
    dims: dict[str, float] = Field(default_factory=dict)
    note: str = ""


class PartSpec(BaseModel):
    part_type: str = "part"
    material: str = "6061"
    process: str = "cnc_milling"
    features: list[Feature] = Field(default_factory=list)
    assertions: Assertions = Field(default_factory=Assertions)
    defaults_used: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    rule: str
    level: Literal["L0", "L1", "L2", "L3"]
    severity: Literal["error", "warning"] = "error"
    target: str = ""
    message: str
    measured: Optional[float] = None
    required: Optional[float] = None
    hint: str = ""
    location: Optional[list[float]] = None  # [x, y, z] mm, script frame (same as part.step / part.glb before the Y-up node rotation)
