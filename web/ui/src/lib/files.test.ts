import { describe, expect, it } from 'vitest';
import { downloadName, fileState, formatSize, groupFiles, safeTitle } from './files';

describe('download names', () => {
  it('sanitises but keeps CJK (same as the backend)', () => {
    expect(safeTitle('L型支架: 100×60/6mm')).toBe('L型支架_100_60_6mm');
    expect(safeTitle('../../etc')).toBe('etc');
    expect(safeTitle('   ')).toBe('part');
    expect(safeTitle('a'.repeat(80))).toHaveLength(60);
  });
  it('builds <title>_v<n>.<ext>', () => {
    expect(downloadName('L型支架', 2, 'part.step')).toBe('L型支架_v2.step');
    expect(downloadName('L型支架', 2, 'drawing.pdf')).toBe('L型支架_v2.pdf');
    expect(downloadName('x', 1, 'render.png')).toBe('x_v1_render.png');
    expect(downloadName('x', 1, 'rounds/r3.glb')).toBe('x_v1_r3.glb');
    expect(downloadName('x', 1, 'bundle.zip')).toBe('x_v1.zip');
  });
});

describe('file grouping and states', () => {
  const base = { files: [] as string[], artifacts: [] as string[], failed: [] as { name: string; message: string }[], running: false };
  it('groups manufacturing / source / records (collapsed)', () => {
    const g = groupFiles({ ...base, files: ['part.step', 'part.py', 'run.json'] }, { 'part.step': 2048 });
    expect(g.map((x) => x.id)).toEqual(['manufacturing', 'source', 'records']);
    expect(g[0].items.map((i) => i.file)).toEqual(['part.step', 'drawing.pdf', 'drawing.dxf']);
    expect(g[0].items[0]).toMatchObject({ state: 'ready', size: 2048 });
    expect(g[0].items[1].state).toBe('missing');
    expect(g[2].collapsed).toBe(true);
  });
  it('pending while running, ready on artifact event, failed on artifact_failed', () => {
    const ctx = { ...base, running: true, artifacts: ['part.step'], failed: [{ name: 'drawing.pdf', message: 'HLR failed' }] };
    expect(fileState('part.step', ctx).state).toBe('ready');
    expect(fileState('part.py', ctx).state).toBe('pending');
    expect(fileState('drawing.pdf', ctx)).toEqual({ state: 'failed', message: 'HLR failed' });
    expect(fileState('drawing.dxf', { ...ctx, failed: [{ name: 'drawing', message: 'x' }] }).state).toBe('failed');
  });
  it('formats sizes', () => {
    expect(formatSize(500)).toBe('500 B');
    expect(formatSize(2048)).toBe('2.0 KB');
    expect(formatSize(48 * 1024)).toBe('48 KB');
    expect(formatSize(3 * 1024 * 1024)).toBe('3.0 MB');
    expect(formatSize(undefined)).toBe('');
  });
});
