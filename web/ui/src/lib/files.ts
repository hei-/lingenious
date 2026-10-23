/** Download file naming and grouping (mirrors web/server/store.py download_name / BUNDLE). */

const SUFFIX: Record<string, string> = {
  'part.step': '.step', 'part.py': '.py', 'part.glb': '.glb', 'drawing.pdf': '.pdf', 'drawing.dxf': '.dxf',
  'drawing.png': '_drawing.png', 'render.png': '_render.png', 'run.json': '_run.json', 'log.txt': '_log.txt', 'bundle.zip': '.zip',
};

/** Keep letters/digits/CJK/._-, collapse everything else to "_", max 60 chars. */
export function safeTitle(title: string): string {
  const t = (title ?? '').trim().replace(/[^\p{L}\p{N}_.-]+/gu, '_').replace(/^[._-]+|[._-]+$/g, '');
  return t.slice(0, 60).replace(/[._-]+$/, '') || 'part';
}

export function downloadName(title: string, version: number, file: string): string {
  const base = `${safeTitle(title)}_v${version}`;
  const m = file.match(/^rounds\/(r\d+)\.glb$/);
  if (m) return `${base}_${m[1]}.glb`;
  return base + (SUFFIX[file] ?? `_${file}`);
}

export type GroupId = 'manufacturing' | 'source' | 'records';
export const FILE_GROUPS: { id: GroupId; files: string[]; collapsed?: boolean }[] = [
  { id: 'manufacturing', files: ['part.step', 'drawing.pdf', 'drawing.dxf'] },
  { id: 'source', files: ['part.py'] },
  { id: 'records', files: ['run.json', 'log.txt'], collapsed: true },
];

export type FileState = 'ready' | 'pending' | 'failed' | 'missing';
export interface FileCtx { files: string[]; artifacts: string[]; failed: { name: string; message: string }[]; running: boolean }

/** Map artifact names to the files they produce (the drawing artifact may be reported as "drawing"). */
function failedFor(file: string, failed: FileCtx['failed']) {
  return failed.find((f) => f.name === file || (file.startsWith('drawing.') && f.name === 'drawing'));
}

export function fileState(file: string, ctx: FileCtx): { state: FileState; message?: string } {
  if (ctx.files.includes(file) || ctx.artifacts.includes(file)) return { state: 'ready' };
  const f = failedFor(file, ctx.failed);
  if (f) return { state: 'failed', message: f.message };
  return { state: ctx.running ? 'pending' : 'missing' };
}

export function groupFiles(ctx: FileCtx, sizes: Record<string, number> = {}) {
  return FILE_GROUPS.map((g) => ({ ...g, items: g.files.map((file) => ({ file, size: sizes[file], ...fileState(file, ctx) })) }));
}

export function formatSize(n?: number): string {
  if (n == null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
