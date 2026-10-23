export type V3 = [number, number, number];

/** Script frame (Z-up, mm) -> glTF/three world (Y-up): the rotation baked into the part.glb root node. */
export function zUpToYUp([x, y, z]: V3): V3 {
  return [x, z, -y];
}

/**
 * Camera pose focusing on `target`: keep the current viewing direction, move to `dist` from the marker.
 * dist is the current distance scaled down, but never closer than 0.35 r nor farther than 3 r (r = model radius).
 */
export function focusPose(target: V3, camPos: V3, curTarget: V3, radius: number): { target: V3; position: V3; dist: number } {
  const d: V3 = [camPos[0] - curTarget[0], camPos[1] - curTarget[1], camPos[2] - curTarget[2]];
  const cur = Math.hypot(...d) || 1;
  const dist = Math.min(3 * radius, Math.max(0.35 * radius, cur * 0.6));
  const k = dist / cur;
  return { target, position: [target[0] + d[0] * k, target[1] + d[1] * k, target[2] + d[2] * k], dist };
}

/** Project a world point to CSS pixels in a w x h viewport given NDC (x,y in [-1,1]). */
export function ndcToPx(x: number, y: number, w: number, h: number): { x: number; y: number } {
  return { x: ((x + 1) / 2) * w, y: ((1 - y) / 2) * h };
}
