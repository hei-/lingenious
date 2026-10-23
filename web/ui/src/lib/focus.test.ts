import { describe, expect, it } from 'vitest';
import { focusPose, ndcToPx, zUpToYUp } from './focus';
import { geometryPlan, initialView, issueId, viewReducer } from './viewstate';
import type { Round } from '../types';

describe('marker math', () => {
  it('maps script Z-up to glTF Y-up', () => {
    expect(zUpToYUp([1, 2, 3])).toEqual([1, 3, -2]);
    expect(zUpToYUp([0, -27, 6])).toEqual([0, 6, 27]);
  });
  it('focus keeps the view direction and clamps the distance', () => {
    const p = focusPose([10, 0, 0], [100, 0, 0], [0, 0, 0], 50);
    expect(p.target).toEqual([10, 0, 0]);
    expect(p.dist).toBeCloseTo(60);
    expect(p.position[0]).toBeCloseTo(70); expect(p.position[1]).toBeCloseTo(0);
    expect(focusPose([0, 0, 0], [1, 0, 0], [0, 0, 0], 50).dist).toBeCloseTo(17.5); // min 0.35 r
    expect(focusPose([0, 0, 0], [1000, 0, 0], [0, 0, 0], 50).dist).toBeCloseTo(150); // max 3 r
  });
  it('ndc to px', () => {
    expect(ndcToPx(0, 0, 200, 100)).toEqual({ x: 100, y: 50 });
    expect(ndcToPx(-1, 1, 200, 100)).toEqual({ x: 0, y: 0 });
  });
});

const rounds: Round[] = [
  { n: 1, seconds: 1, issues: [], glb: 'rounds/r1.glb' },
  { n: 2, seconds: 1, issues: [], glb: 'rounds/r2.glb' },
  { n: 3, seconds: 1, issues: [], glb: 'rounds/r3.glb' },
];

describe('view state', () => {
  it('selecting a round and going back to final', () => {
    let s = viewReducer(initialView, { type: 'round', n: 1 });
    expect(geometryPlan(s, rounds)).toMatchObject({ mainRound: 1, chipRound: 1, markersRound: 1 });
    s = viewReducer(s, { type: 'round', n: null });
    expect(geometryPlan(s, rounds)).toMatchObject({ mainRound: null, chipRound: null, markersRound: 3 });
  });
  it('last round is the final geometry; rounds without glb fall back to final', () => {
    expect(geometryPlan(viewReducer(initialView, { type: 'round', n: 3 }), rounds).mainRound).toBeNull();
    const r2 = rounds.map((r) => (r.n === 2 ? { ...r, glb: undefined } : r));
    expect(geometryPlan(viewReducer(initialView, { type: 'round', n: 2 }), r2).mainRound).toBeNull();
  });
  it('compare draws the failed round over the next one and ends on final', () => {
    const s = viewReducer(initialView, { type: 'compare', n: 1 });
    expect(geometryPlan(s, rounds)).toMatchObject({ ghostRound: 1, mainRound: 2, markersRound: 1 });
    expect(geometryPlan(viewReducer(initialView, { type: 'compare', n: 2 }), rounds)).toMatchObject({ ghostRound: 2, mainRound: null });
    expect(viewReducer(s, { type: 'compare', n: 1 }).compare).toBeNull(); // toggle off
  });
  it('focusing an issue toggles and can switch round', () => {
    const id = issueId(1, 0);
    let s = viewReducer(initialView, { type: 'issue', id, round: 1 });
    expect(s).toEqual({ round: 1, compare: null, issue: 'r1:0' });
    s = viewReducer(s, { type: 'issue', id });
    expect(s.issue).toBeNull();
    expect(viewReducer(s, { type: 'reset' })).toEqual(initialView);
  });
});
