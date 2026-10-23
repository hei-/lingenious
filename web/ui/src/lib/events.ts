import type { Issue, LiveEvent, PartSpec, Round, RunJson, Usage } from '../types';

export interface LiveState {
  phase: 'idle' | 'parsing' | 'spec' | 'generating' | 'fixing' | 'done' | 'error';
  spec?: PartSpec;
  rounds: Round[];
  fixing?: number;
  artifacts: string[];
  failedArtifacts: { name: string; message: string }[];
  status?: string;
  usage?: Usage;
  error?: string;
  version?: number;
}

export const initialLive: LiveState = { phase: 'idle', rounds: [], artifacts: [], failedArtifacts: [] };

export function reduceEvent(s: LiveState, ev: LiveEvent): LiveState {
  switch (ev.type) {
    case 'parsing': return { ...initialLive, phase: 'parsing' };
    case 'spec': return { ...s, phase: 'spec', spec: ev.data };
    case 'generating': return { ...s, phase: 'generating' };
    case 'round': {
      // replayed events must be idempotent: replace a round with the same n
      const rounds = s.rounds.filter((r) => r.n !== ev.data.n).concat([{ ...ev.data }]).sort((a, b) => a.n - b.n);
      return { ...s, rounds, phase: s.phase === 'done' ? 'done' : 'generating', fixing: undefined };
    }
    case 'fixing': return { ...s, phase: 'fixing', fixing: ev.data.n };
    case 'artifact': return s.artifacts.includes(ev.data.name) ? s : { ...s, artifacts: [...s.artifacts, ev.data.name] };
    case 'artifact_failed': return { ...s, failedArtifacts: [...s.failedArtifacts.filter((a) => a.name !== ev.data.name), ev.data] };
    case 'done': return { ...s, phase: 'done', status: ev.data.status, usage: ev.data.usage, version: ev.data.version, fixing: undefined };
    case 'error': return { ...s, phase: 'error', error: ev.data.message, fixing: undefined };
  }
}

export function replay(events: LiveEvent[], from: LiveState = initialLive): LiveState {
  return events.reduce(reduceEvent, from);
}

/** A round passes when code ran and no error-severity issue remains. */
export function roundPassed(r: Round): boolean {
  return r.exec_ok !== false && !r.issues.some((i) => i.severity === 'error');
}

export function countByLevel(issues: Issue[]): { level: string; error: number; warning: number }[] {
  const m = new Map<string, { error: number; warning: number }>();
  for (const i of issues) {
    const e = m.get(i.level) ?? { error: 0, warning: 0 };
    e[i.severity === 'error' ? 'error' : 'warning']++;
    m.set(i.level, e);
  }
  return [...m.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([level, v]) => ({ level, ...v }));
}

/** Static state of a finished run.json, same shape as the live state. */
export function liveFromRunJson(run: RunJson): LiveState {
  const failed = run.status !== 'success';
  return {
    phase: 'done', spec: run.spec, rounds: run.rounds ?? [], artifacts: [], failedArtifacts: [],
    status: run.status, usage: run.usage, error: failed && (run.rounds ?? []).length === 0 && run.status !== 'need_info' ? run.status : undefined,
  };
}
