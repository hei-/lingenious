import { describe, expect, it } from 'vitest';
import { countByLevel, initialLive, liveFromRunJson, reduceEvent, replay, roundPassed } from './events';
import type { Issue, LiveEvent } from '../types';

const err: Issue = { rule: 'internal_corner_radius', level: 'L3', severity: 'error', message: 'm' };
const warn: Issue = { rule: 'x', level: 'L3', severity: 'warning', message: 'm' };

const stream: LiveEvent[] = [
  { type: 'parsing' },
  { type: 'spec', data: { part_type: 'L' } },
  { type: 'generating' },
  { type: 'round', data: { n: 1, seconds: 3.6, exec_ok: true, issues: [err] } },
  { type: 'fixing', data: { n: 2 } },
  { type: 'round', data: { n: 2, seconds: 2.1, exec_ok: true, issues: [warn] } },
  { type: 'artifact', data: { name: 'part.step' } },
  { type: 'done', data: { status: 'success', version: 1 } },
];

describe('event reducer', () => {
  it('walks the phases', () => {
    expect(reduceEvent(initialLive, stream[0]).phase).toBe('parsing');
    const mid = replay(stream.slice(0, 5));
    expect(mid.phase).toBe('fixing');
    expect(mid.fixing).toBe(2);
    expect(mid.rounds).toHaveLength(1);
  });
  it('finishes with done and passes on warnings only', () => {
    const s = replay(stream);
    expect(s.phase).toBe('done');
    expect(s.status).toBe('success');
    expect(s.rounds.map(roundPassed)).toEqual([false, true]);
    expect(s.artifacts).toEqual(['part.step']);
  });
  it('is idempotent when events are replayed after reconnect', () => {
    const once = replay(stream);
    const twice = replay([...stream.slice(0, 4), ...stream]);
    expect(twice.rounds).toEqual(once.rounds);
    expect(twice.artifacts).toEqual(once.artifacts);
  });
  it('records errors', () => {
    const s = replay([{ type: 'parsing' }, { type: 'error', data: { message: 'boom' } }]);
    expect(s.phase).toBe('error');
    expect(s.error).toBe('boom');
  });
  it('counts issues by level and builds state from run.json', () => {
    expect(countByLevel([err, warn, { ...err, level: 'L1' }])).toEqual([
      { level: 'L1', error: 1, warning: 0 }, { level: 'L3', error: 1, warning: 1 }]);
    const s = liveFromRunJson({ status: 'success', rounds: [{ n: 1, seconds: 1, issues: [] }] });
    expect(s.phase).toBe('done');
  });
});
