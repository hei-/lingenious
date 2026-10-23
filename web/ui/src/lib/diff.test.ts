import { describe, expect, it } from 'vitest';
import { collapseContext, diffLines, diffStats } from './diff';

describe('diffLines', () => {
  it('detects no change', () => {
    const ops = diffLines('a\nb', 'a\nb');
    expect(ops.every((o) => o.type === 'eq')).toBe(true);
  });
  it('detects add / del / replace', () => {
    const ops = diffLines('a\nb\nc', 'a\nx\nc\nd');
    expect(diffStats(ops)).toEqual({ add: 2, del: 1 });
    expect(ops.find((o) => o.type === 'del')?.text).toBe('b');
  });
  it('treats empty old as all additions with line numbers', () => {
    const ops = diffLines('', 'a\nb');
    expect(ops).toEqual([{ type: 'add', text: 'a', b: 1 }, { type: 'add', text: 'b', b: 2 }]);
  });
  it('reconstructs the new text from eq+add', () => {
    const a = 'p\nq\nr\ns\nt', b = 'p\nr\nS\nt\nu';
    const ops = diffLines(a, b);
    expect(ops.filter((o) => o.type !== 'del').map((o) => o.text).join('\n')).toBe(b);
    expect(ops.filter((o) => o.type !== 'add').map((o) => o.text).join('\n')).toBe(a);
  });
  it('collapses long unchanged runs', () => {
    const a = Array.from({ length: 30 }, (_, i) => `l${i}`).join('\n');
    const rows = collapseContext(diffLines(a, a.replace('l15', 'X')), 2);
    expect(rows.some((r) => r.type === 'gap')).toBe(true);
    expect(rows.length).toBeLessThan(15);
  });
});
