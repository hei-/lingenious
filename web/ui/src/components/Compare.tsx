import { useEffect, useMemo, useState } from 'react';
import { api, fetchText } from '../api';
import type { RunDetail } from '../types';
import { useI18n } from '../i18n';
import { DiffView } from './DiffView';
import { Viewer } from './LazyViewer';
import { bboxDims } from '../lib/util';

function flatten(run: RunDetail['versions'][number]['run']) {
  const m = new Map<string, number>();
  for (const f of run?.spec?.features ?? []) for (const [k, v] of Object.entries(f.dims)) m.set(`${f.id}.${k}`, v);
  const bb = run?.spec?.assertions?.bbox;
  if (bb) { m.set('bbox.x', bb.x); m.set('bbox.y', bb.y); m.set('bbox.z', bb.z); }
  return m;
}

export function Compare({ detail, current }: { detail: RunDetail; current: number }) {
  const { t } = useI18n();
  const done = detail.versions.filter((v) => v.run);
  const [a, setA] = useState(() => (done.length > 1 ? done[done.length - 2].version : current));
  const [b, setB] = useState(current);
  const [codes, setCodes] = useState<{ a: string | null; b: string | null }>({ a: null, b: null });
  useEffect(() => { if (!done.some((v) => v.version === b)) setB(done[done.length - 1]?.version ?? current); /* eslint-disable-next-line */ }, [detail.versions.length]);
  useEffect(() => {
    let live = true;
    setCodes({ a: null, b: null });
    const get = (v: number) => fetchText(api.fileUrl(detail.id, v, 'part.py')).catch(() => '');
    Promise.all([get(a), get(b)]).then(([x, y]) => live && setCodes({ a: x, b: y }));
    return () => { live = false; };
  }, [detail.id, a, b]);

  const va = done.find((v) => v.version === a), vb = done.find((v) => v.version === b);
  const rows = useMemo(() => {
    const ma = flatten(va?.run ?? null), mb = flatten(vb?.run ?? null);
    const keys = [...new Set([...ma.keys(), ...mb.keys()])];
    return keys.filter((k) => ma.get(k) !== mb.get(k)).map((k) => ({ k, a: ma.get(k), b: mb.get(k) }));
  }, [va, vb]);

  if (done.length < 2) return <div className="empty">{t('compareNeed')}</div>;
  const sel = (label: string, v: number, set: (n: number) => void) => (
    <label className="sel"><span>{label}</span>
      <select value={v} onChange={(e) => set(Number(e.target.value))}>{done.map((x) => <option key={x.version} value={x.version}>v{x.version}</option>)}</select>
    </label>
  );
  const pane = (ver: typeof va, n: number) => (
    <Viewer compact url={ver && (ver.files.length === 0 || ver.files.includes('part.glb')) ? api.fileUrl(detail.id, n, 'part.glb') : null} fallbackDims={bboxDims(ver?.run?.spec)} label={`v${n}`} />
  );
  return (
    <div className="compare">
      <div className="compare-grid">
        <div>{sel(t('compareA'), a, setA)}{pane(va, a)}</div>
        <div>{sel(t('compareB'), b, setB)}{pane(vb, b)}</div>
      </div>
      <h3>{t('paramDiff')}</h3>
      {rows.length === 0 ? <p className="muted">{t('paramSame')}</p> : (
        <div className="table-scroll"><table className="tbl num">
          <thead><tr><th>{t('param')}</th><th>v{a}</th><th>v{b}</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.k}><th scope="row"><code>{r.k}</code></th><td className="del-t">{r.a ?? '—'}</td><td className="add-t">{r.b ?? '—'}</td></tr>)}</tbody>
        </table></div>
      )}
      <h3>{t('codeDiff')} <span className="muted num">v{a} → v{b}</span></h3>
      {codes.a === null || codes.b === null ? <p className="muted"><span className="spinner sm" /> {t('loadingCode')}</p> : <DiffView oldText={codes.a} newText={codes.b} />}
    </div>
  );
}
