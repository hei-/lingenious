import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, fetchText, setUnauthorizedHandler } from './api';

const resp = (status: number, body: unknown = {}) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

afterEach(() => { setUnauthorizedHandler(null); vi.unstubAllGlobals(); });

describe('global 401 handling', () => {
  it('calls the handler and rejects with ApiError(401)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => resp(401, { detail: 'unauthorized' })));
    const h = vi.fn(); setUnauthorizedHandler(h);
    await expect(api.listRuns()).rejects.toMatchObject({ status: 401 });
    await expect(api.listRuns()).rejects.toBeInstanceOf(ApiError);
    expect(h).toHaveBeenCalledTimes(2);
  });
  it('also covers text downloads', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('no', { status: 401 })));
    const h = vi.fn(); setUnauthorizedHandler(h);
    await expect(fetchText('/api/runs/x/v1/part.py')).rejects.toMatchObject({ status: 401 });
    expect(h).toHaveBeenCalledTimes(1);
  });
  it('does not fire for other errors or success', async () => {
    const h = vi.fn(); setUnauthorizedHandler(h);
    vi.stubGlobal('fetch', vi.fn(async () => resp(404, { detail: 'nope' })));
    await expect(api.listRuns()).rejects.toMatchObject({ status: 404 });
    vi.stubGlobal('fetch', vi.fn(async () => resp(200, [])));
    await expect(api.listRuns()).resolves.toEqual([]);
    expect(h).not.toHaveBeenCalled();
  });
});
