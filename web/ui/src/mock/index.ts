/**
 * Mock layer: replays examples/bracket/v1 (copied to public/mock/) and simulates SSE timing.
 * Enabled by ?mock=1, or automatically in dev when /api/health fails.
 */
import type { Api, StreamStatus } from '../api';
import type { LiveEvent, RunDetail, RunJson, RunStatus, RunSummary } from '../types';

const BASE = (import.meta.env.BASE_URL ?? '/') + 'mock/';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const SPEED = 1; // multiply delays

let templ: { run: RunJson; code: string } | null = null;
async function template() {
  if (templ) return templ;
  const [run, code] = await Promise.all([fetch(BASE + 'run.json').then((r) => r.json() as Promise<RunJson>), fetch(BASE + 'part.py').then((r) => r.text())]);
  // run.json has no per-round code: synthesise round 1 by dropping the fillet block the DFM rule complained about
  const r1 = code.replace(/# -+ feature: inner_fillet[\s\S]*?(?=# -+ feature: hole1)/, '');
  // new contract fields: per-round geometry, issue locations (script frame, Z-up mm), reconstructed flag
  run.rounds = run.rounds.map((r, i) => ({
    ...r, code: i === 0 ? r1 : code, glb: `rounds/r${r.n}.glb`, ...(i === 0 ? { reconstructed: true } : {}),
    issues: r.issues.map((x) => (x.rule === 'internal_corner_radius' ? { ...x, location: [0, -27, 6] as [number, number, number], location2: [-50, -27, 6] as [number, number, number] } : x)),
  }));
  templ = { run, code };
  return templ;
}

interface MockVersion { events: LiveEvent[]; finished: boolean; run: RunJson | null; code: string }
interface MockRun { id: string; request: string; material: string; created_at: string; versions: Record<number, MockVersion>; example?: boolean }
const store = new Map<string, MockRun>();
let counter = 0;

function statusOf(m: MockRun): RunStatus {
  const vs = Object.values(m.versions);
  if (vs.some((v) => !v.finished)) return 'running';
  return (vs[vs.length - 1]?.run?.status ?? 'success') as RunStatus;
}

async function ensureExample() {
  if (store.has('example-bracket')) return;
  const { run } = await template();
  const events = eventsFor(run);
  store.set('example-bracket', {
    id: 'example-bracket', example: true, material: '6061', created_at: '2026-05-01T09:00:00Z',
    request: 'L 型铝支架:底板 100×60×6mm,立板沿长边,高 40mm、厚 3mm,底板四角各一个 M6 通孔,立板中间一个直径 20 的圆孔。',
    versions: { 1: { events, finished: true, run, code: templ!.code } },
  });
}

function eventsFor(run: RunJson): LiveEvent[] {
  const ev: LiveEvent[] = [{ type: 'parsing' }, { type: 'spec', data: run.spec! }, { type: 'generating' }];
  run.rounds.forEach((r, i) => {
    ev.push({ type: 'round', data: { n: r.n, seconds: r.seconds, exec_ok: true, issues: r.issues } });
    if (i < run.rounds.length - 1) ev.push({ type: 'fixing', data: { n: r.n + 1 } });
  });
  ev.push({ type: 'artifact', data: { name: 'part.step' } }, { type: 'done', data: { status: run.status, usage: run.usage } });
  return ev;
}

const listeners = new Map<string, Set<(e: LiveEvent) => void>>();
const key = (id: string, v: number) => `${id}#${v}`;

async function play(m: MockRun, v: number, events: LiveEvent[]) {
  const ver = m.versions[v];
  for (const e of events) {
    const delay = e.type === 'round' ? 1800 : e.type === 'generating' ? 1400 : e.type === 'fixing' ? 600 : 900;
    await sleep(delay * SPEED);
    ver.events.push(e);
    listeners.get(key(m.id, v))?.forEach((fn) => fn(e));
  }
  ver.finished = true;
}

function toDetail(m: MockRun): RunDetail {
  return {
    id: m.id, title: m.request.slice(0, 40), request: m.request, material: m.material, process: 'cnc_milling',
    status: statusOf(m), created_at: m.created_at, readOnly: !!m.example,
    versions: Object.entries(m.versions).map(([n, v]) => ({
      version: Number(n), run: v.finished ? v.run : null,
      files: v.finished ? ['part.step', 'part.py', 'part.glb', ...(v.run?.rounds ?? []).map((r) => r.glb as string), 'render.png', 'drawing.pdf', 'drawing.dxf', 'drawing.png', 'run.json', 'log.txt'] : [],
    })),
  };
}
const summary = (m: MockRun): RunSummary => {
  const vs = Object.keys(m.versions).map(Number);
  return { id: m.id, title: m.request.slice(0, 40), status: statusOf(m), created_at: m.created_at, versions: vs,
    ...(m.example ? { request: m.request, rounds: m.versions[vs[vs.length - 1]].run?.rounds.length, thumb: BASE + 'thumb.png', thumbFallback: BASE + 'render.png' } : {}) };
};

function modifiedRun(base: RunJson, baseCode: string, change: string): { run: RunJson; code: string } {
  const m = change.match(/(\d+(?:\.\d+)?)\s*(?:mm|毫米)?/);
  const t = m ? Number(m[1]) : 4;
  const code = baseCode.replace(/WALL_T = [\d.]+/, `WALL_T = ${t}.0`);
  const spec = JSON.parse(JSON.stringify(base.spec));
  for (const f of spec.features) if (f.id === 'vertical_plate') f.dims.thickness = t;
  spec.assertions.bbox.y = 60;
  return { code, run: { status: 'success', spec, rounds: [{ n: 1, seconds: 2.4, exec_ok: true, issues: [], code, glb: 'rounds/r2.glb' }], final_issues: [], usage: { calls: 1, prompt_tokens: 2100, completion_tokens: 900 } } };
}

export const mockApi: Api = {
  async health() { await sleep(80); return { ok: true, llm_configured: true }; },
  async listRuns() { await ensureExample(); return [...store.values()].filter((r) => !r.example).reverse().map(summary); },
  async listExamples() { await ensureExample(); return [...store.values()].filter((r) => r.example).map(summary); },
  async getRun(id) {
    await ensureExample(); await sleep(60);
    const m = store.get(id);
    if (!m) throw Object.assign(new Error('not found'), { status: 404 });
    return toDetail(m);
  },
  async createRun(body) {
    const { run, code } = await template();
    const id = `mock-${++counter}`;
    const m: MockRun = { id, request: body.request, material: body.material ?? '6061', created_at: new Date().toISOString(), versions: { 1: { events: [], finished: false, run, code } } };
    store.set(id, m);
    void play(m, 1, eventsFor(run));
    return { id };
  },
  async modify(id, change) {
    const m = store.get(id);
    if (!m || m.example) throw new Error('read-only');
    const { run } = await template();
    const n = Math.max(...Object.keys(m.versions).map(Number)) + 1;
    const prev = m.versions[n - 1];
    const mod = modifiedRun(run, prev.code, change);
    m.versions[n] = { events: [], finished: false, run: mod.run, code: mod.code };
    void play(m, n, eventsFor(mod.run));
    return { id, version: n };
  },
  subscribe(id, version, onEvent, onStatus) {
    let closed = false;
    const k = key(id, version);
    const set = listeners.get(k) ?? new Set();
    listeners.set(k, set);
    const fn = (e: LiveEvent) => { if (!closed) onEvent(e); };
    void (async () => {
      await sleep(40);
      const ver = store.get(id)?.versions[version];
      onStatus?.('open');
      ver?.events.slice().forEach(fn); // replay then continue live
      set.add(fn);
    })();
    return () => { closed = true; set.delete(fn); };
  },
  downloadUrl: (id, v, file) => mockApi.fileUrl(id, v, file),
  bundleUrl: () => null,
  fileUrl: (id, v, file) => {
    const code = store.get(id)?.versions[v]?.code;
    if (file === 'part.py' && code) return 'data:text/plain;charset=utf-8,' + encodeURIComponent(code);
    return BASE + file; // same image assets for every version
  },
};
export type { StreamStatus };
