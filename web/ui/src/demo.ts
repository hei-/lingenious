/**
 * Static demo (build with VITE_DEMO=1): read-only API over files exported by scripts/export_demo.py
 * (demo-data/examples.json + demo-data/runs/<id>/v<n>/<file>), so the UI can be hosted on GitHub Pages
 * without a backend. Only the bundled examples are available; creating runs and edits is disabled.
 */
import type { Api } from './api';
import { normalizeDetail } from './api';
import type { RunJson, RunSummary } from './types';

const BASE = (import.meta.env.BASE_URL ?? './') + 'demo-data/';

/** one entry of GET /api/examples (fields used here; normalizeDetail reads the rest) */
interface ExampleRaw { id: string; title: string; status: RunSummary['status']; created_at: string; request: string; versions: number[];
  runs?: Record<string, RunJson>; files?: Record<string, string[]>; version_status?: Record<string, string> }

let raw: Promise<ExampleRaw[]> | null = null;
function examples(): Promise<ExampleRaw[]> {
  raw ??= fetch(BASE + 'examples.json').then((r) => {
    if (!r.ok) throw new Error(`${r.status} examples.json`);
    return r.json() as Promise<ExampleRaw[]>;
  });
  return raw;
}

const notFound = () => Object.assign(new Error('not found'), { status: 404 });
const readOnly = () => Object.assign(new Error('read-only demo'), { status: 403 });

export const demoApi: Api = {
  async health() { return { ok: true, llm_configured: false, demo: true }; },
  async listRuns() { return []; },
  async listExamples() {
    return (await examples()).map((r): RunSummary => {
      const vs = r.versions as number[];
      const files: string[] = r.files?.[String(vs[0])] ?? [];
      return { id: r.id, title: r.title, status: r.status, created_at: r.created_at, versions: vs, request: r.request,
        rounds: r.runs?.[String(vs[0])]?.rounds?.length,
        thumb: demoApi.fileUrl(r.id, vs[0], files.includes('thumb.png') ? 'thumb.png' : 'render.png'), thumbFallback: demoApi.fileUrl(r.id, vs[0], 'render.png') };
    });
  },
  async getRun(id) {
    const r = (await examples()).find((x) => x.id === id);
    if (!r) throw notFound();
    return normalizeDetail(r);
  },
  async createRun() { throw readOnly(); },
  async modify() { throw readOnly(); },
  subscribe(id, version, onEvent, onStatus) {
    // examples are finished runs: the server also replays a single "done" for them
    let closed = false;
    void examples().then((all) => {
      if (closed) return;
      const r = all.find((x) => x.id === id);
      onStatus?.('open');
      onEvent({ type: 'done', data: { status: r?.version_status?.[String(version)] ?? 'success', version } });
    });
    return () => { closed = true; };
  },
  fileUrl: (id, v, file) => `${BASE}runs/${encodeURIComponent(id)}/v${v}/${file}`,
  downloadUrl: (id, v, file) => demoApi.fileUrl(id, v, file),
  bundleUrl: () => null,
};
