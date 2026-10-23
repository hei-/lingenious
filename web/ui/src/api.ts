import type { Health, LiveEvent, RunDetail, RunSummary, VersionInfo, RunJson } from './types';
import { EVENT_NAMES } from './types';
import * as mock from './mock';
import { demoApi } from './demo';

export const MAX_REQUEST_LEN = 2000;

let mockMode = typeof location !== 'undefined' && new URLSearchParams(location.search).get('mock') === '1';
export const isMock = () => mockMode;
/** static read-only demo (VITE_DEMO=1 build for GitHub Pages), see demo.ts */
export const isDemo = import.meta.env.VITE_DEMO === '1';
export function enableMock() { mockMode = true; }

export type StreamStatus = 'open' | 'lost';
export interface Api {
  health(): Promise<Health>;
  listRuns(): Promise<RunSummary[]>;
  listExamples(): Promise<RunSummary[]>;
  getRun(id: string): Promise<RunDetail>;
  createRun(body: { request: string; material?: string; process?: string }): Promise<{ id: string }>;
  modify(id: string, change: string): Promise<{ id: string; version: number }>;
  subscribe(id: string, version: number, onEvent: (e: LiveEvent) => void, onStatus?: (s: StreamStatus) => void): () => void;
  fileUrl(id: string, version: number, file: string): string;
  /** attachment URL (server sets Content-Disposition with a readable name) */
  downloadUrl(id: string, version: number, file: string): string;
  /** zip of the version's user-facing files; null when unavailable (mock) */
  bundleUrl(id: string, version: number): string | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** Called on any 401 from the API (token missing/expired); the app then shows the login screen. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(f: (() => void) | null) { onUnauthorized = f; }

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } });
  if (r.status === 401 && !path.startsWith('/api/auth/')) onUnauthorized?.();
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const b = await r.json(); msg = b.detail ? (typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail)) : b.message ?? msg; } catch { /* not json */ }
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}

/** GET /api/runs/{id} and each /api/examples entry: meta + runs {"1": run.json|null} + files {"1": [names]} (docs/web-app.md). */
export function normalizeDetail(raw: any): RunDetail {
  const runs: Record<string, RunJson | null> = raw.runs ?? {};
  const files: Record<string, string[]> = raw.files ?? {};
  const vs: Record<string, string> = raw.version_status ?? {};
  const versions: VersionInfo[] = (raw.versions as number[]).slice().sort((a, b) => a - b).map((n) => ({
    version: n, run: runs[String(n)] ?? null, files: files[String(n)] ?? [], status: vs[String(n)],
    change: raw.changes?.[String(n)], synthetic: raw.synthetic?.[String(n)], sizes: raw.file_sizes?.[String(n)] ?? {},
  }));
  return {
    id: raw.id, title: raw.title || (raw.request ?? '').slice(0, 40), request: raw.request ?? '',
    material: raw.material, process: raw.process, status: raw.status, created_at: raw.created_at,
    readOnly: !!raw.example, versions, selection: raw.selection ?? undefined,
  };
}

const real: Api = {
  health: () => j<Health>('/api/health'),
  listRuns: () => j<RunSummary[]>('/api/runs'),
  listExamples: async () => {
    const raw = await j<any[]>('/api/examples');
    return raw.map((r) => {
      const vs = r.versions as number[];
      const last = r.runs?.[String(vs[0])]; // the LLM-driven first version (later ones may be edits)
      return { id: r.id, title: r.title, status: r.status, created_at: r.created_at, versions: vs, request: r.request, rounds: last?.rounds?.length,
        thumb: real.fileUrl(r.id, vs[0], (r.files?.[String(vs[0])] ?? []).includes('thumb.png') ? 'thumb.png' : 'render.png'), thumbFallback: real.fileUrl(r.id, vs[0], 'render.png') };
    });
  },
  getRun: async (id) => normalizeDetail(await j<unknown>(`/api/runs/${encodeURIComponent(id)}`)),
  createRun: (body) => j('/api/runs', { method: 'POST', body: JSON.stringify(body) }),
  modify: (id, change) => j(`/api/runs/${encodeURIComponent(id)}/modify`, { method: 'POST', body: JSON.stringify({ change }) }),
  subscribe(id, version, onEvent, onStatus) {
    const es = new EventSource(`/api/runs/${encodeURIComponent(id)}/events?version=${version}`);
    es.onopen = () => onStatus?.('open');
    for (const name of EVENT_NAMES) {
      es.addEventListener(name, (m) => {
        let data: unknown = {};
        try { data = JSON.parse((m as MessageEvent).data || '{}'); } catch { /* ignore bad payload */ }
        onEvent({ type: name, data } as LiveEvent);
        if (name === 'done' || name === 'error') es.close();
      });
    }
    es.onerror = () => {
      onStatus?.('lost');
      // EventSource hides the HTTP status: probe health to learn whether the session expired
      fetch('/api/health').then((r) => r.json()).then((h: Health) => { if (h.auth_required && !h.authenticated) onUnauthorized?.(); }).catch(() => { /* offline */ });
    };
    return () => es.close();
  },
  fileUrl: (id, v, file) => `/api/runs/${encodeURIComponent(id)}/v${v}/${file}`,
  downloadUrl: (id, v, file) => `/api/runs/${encodeURIComponent(id)}/v${v}/${file}?download=1`,
  bundleUrl: (id, v) => `/api/runs/${encodeURIComponent(id)}/v${v}/bundle.zip`,
};

export const api: Api = new Proxy(real, {
  get: (t, k: keyof Api) => (isDemo ? demoApi[k] : mockMode ? (mock.mockApi as Api)[k] : t[k]),
});

export async function fetchText(url: string): Promise<string> {
  const r = await fetch(url);
  if (r.status === 401) onUnauthorized?.();
  if (!r.ok) throw new ApiError(r.status, r.statusText);
  const t = await r.text();
  if (/^\s*<!doctype html/i.test(t)) throw new ApiError(404, 'not found'); // SPA fallback
  return t;
}

/** Cookie session (HttpOnly) for the optional access token; not part of the mockable Api. */
export const auth = {
  login: (token: string) => j<{ ok: boolean }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ token }) }),
  logout: () => j<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
};
