import type { Round } from '../types';

/** Which geometry / markers the 3D view shows. null round = final result. */
export interface ViewState { round: number | null; compare: number | null; issue: string | null }
export const initialView: ViewState = { round: null, compare: null, issue: null };

export type ViewAction =
  | { type: 'round'; n: number | null }
  | { type: 'compare'; n: number }
  | { type: 'issue'; id: string | null; round?: number | null }
  | { type: 'reset' };

export const issueId = (round: number, index: number) => `r${round}:${index}`;

export function viewReducer(s: ViewState, a: ViewAction): ViewState {
  switch (a.type) {
    case 'reset': return initialView;
    case 'round': return { round: a.n, compare: null, issue: null };
    case 'compare': return s.compare === a.n ? { ...s, compare: null, issue: null } : { round: a.n, compare: a.n, issue: null };
    case 'issue': return { ...s, round: a.round === undefined ? s.round : a.round, issue: s.issue === a.id ? null : a.id };
  }
}

export interface GeometryPlan {
  mainRound: number | null; // null = final geometry (part.glb)
  ghostRound: number | null; // failed geometry drawn translucent over main
  markersRound: number; // whose issues are marked
  chipRound: number | null; // "Round N geometry" chip (null = viewing final)
}

/** Resolve what to draw. `rounds` must be sorted; the last round is the final one. */
export function geometryPlan(s: ViewState, rounds: Round[]): GeometryPlan {
  const lastN = rounds.length ? rounds[rounds.length - 1].n : 1;
  const hasGlb = (n: number) => !!rounds.find((r) => r.n === n)?.glb;
  if (s.compare != null) {
    const next = rounds.find((r) => r.n > s.compare!);
    const mainRound = !next || next.n === lastN ? null : hasGlb(next.n) ? next.n : null;
    return { mainRound, ghostRound: hasGlb(s.compare) ? s.compare : null, markersRound: s.compare, chipRound: null };
  }
  if (s.round != null && s.round !== lastN && hasGlb(s.round)) return { mainRound: s.round, ghostRound: null, markersRound: s.round, chipRound: s.round };
  return { mainRound: null, ghostRound: null, markersRound: lastN, chipRound: null };
}
