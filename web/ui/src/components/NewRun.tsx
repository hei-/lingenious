import { useRef, useState } from 'react';
import { EXAMPLE_PROMPTS, useI18n, type Key } from '../i18n';
import { MAX_REQUEST_LEN } from '../api';
import type { Health, RunSummary } from '../types';

const MATERIALS = ['6061', '7075', 'steel', '304', 'abs'];
const PROCESSES = ['cnc_milling', 'cnc_turning', '3_axis'];

interface Props { health: Health | null; healthLoading: boolean; onCreate: (b: { request: string; material: string; process: string }) => Promise<void>; firstExample: string | null; examples: RunSummary[] | null }

export function NewRun({ health, healthLoading, onCreate, firstExample, examples }: Props) {
  const { t, lang, errMsg } = useI18n();
  const [request, setRequest] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [material, setMaterial] = useState('6061');
  const [process, setProcess] = useState('cnc_milling');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const off = !!health && !health.llm_configured;
  const demo = !!health?.demo;
  const unknown = !health && !healthLoading;
  const real = (examples ?? []).filter((e) => e.request).slice(0, 3);
  const curated = EXAMPLE_PROMPTS[lang].slice(1);
  const cards = [
    ...real.map((e) => ({
      key: e.id, id: e.id as string | null, title: e.title, request: e.request!, thumb: e.thumb ?? null, fallback: e.thumbFallback ?? null,
      tag: e.status !== 'success' ? t('tagNotPassed') : (e.rounds ?? 1) > 1 ? t('tagRounds', { n: e.rounds ?? 1 }) : t('tagFirst'),
      tone: e.status === 'success' ? 'ok' : 'warn',
    })),
    ...curated.slice(0, Math.max(0, 3 - real.length)).map((p, i) => ({ key: `c${i}`, id: null, title: p.split(/[:,，,。]/)[0], request: p, thumb: null, fallback: null, tag: t('tagPrompt'), tone: '' })),
  ];
  const validation = request.trim().length === 0 ? null : request.trim().length < 6 ? t('reqTooShort') : request.length > MAX_REQUEST_LEN ? t('reqTooLong', { n: MAX_REQUEST_LEN }) : null;

  const disabledReason = off ? t(demo ? 'demoOff' : 'llmOff') : !request.trim() ? t('reqEmpty') : validation;
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const formRef = useRef<HTMLFormElement>(null);
  const prompts = cards.filter((c) => !c.id);
  const examplesOnly = cards.filter((c) => c.id);
  const applyPrompt = (p: string) => { setRequest(p); taRef.current?.focus(); taRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (off || busy || validation || !request.trim()) return;
    setBusy(true); setErr(null);
    try { await onCreate({ request: request.trim(), material, process }); } catch (x) { setErr(errMsg(x)); setBusy(false); }
  };

  return (
    <div className="page narrow">
      <header className="hero">
        <h1>{t('wTitle')}</h1>
        <p className="muted">{t('wSub')}</p>
        {off && (
          <div className="notice warn" role="alert">
            <strong>{t(demo ? 'demoOff' : 'llmOff')}</strong>
            <p>{t(demo ? 'demoOffHint' : 'llmOffHint')}</p>
            {firstExample && <a className="btn sm" href={`#/run/${firstExample}`}>{t('examples')} →</a>}
          </div>
        )}
        {unknown && <div className="notice err" role="alert">{t('loadFailed')}: /api/health</div>}
        <form ref={formRef} onSubmit={submit} className="form hero-form" aria-busy={busy}>
          <label htmlFor="req" className="sr-only">{t('reqLabel')}</label>
          <textarea ref={taRef} id="req" rows={4} value={request} onChange={(e) => setRequest(e.target.value)} placeholder={t('reqPlaceholder')} disabled={off || busy}
            aria-invalid={!!validation} aria-describedby="req-help req-why"
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); formRef.current?.requestSubmit(); } }} />
          <div id="req-help" className="help">
            <span className={validation ? 'err-t' : 'muted'}>{validation ?? ''}</span>
            <span className="num muted">{request.length}/{MAX_REQUEST_LEN}</span>
          </div>
          <div className="controls">
            <label className="sel inline"><span>{t('material')}</span>
              <select value={material} onChange={(e) => setMaterial(e.target.value)} disabled={off || busy}>{MATERIALS.map((m) => <option key={m} value={m}>{t(`mat_${m}` as Key)}</option>)}</select>
            </label>
            <label className="sel inline"><span>{t('process')}</span>
              <select value={process} onChange={(e) => setProcess(e.target.value)} disabled={off || busy}>{PROCESSES.map((m) => <option key={m} value={m}>{t(`proc_${m}` as Key)}</option>)}</select>
            </label>
            <span className="spacer" />
            <span className="kbd-hint muted small" aria-hidden="true"><kbd>{isMac ? '⌘' : 'Ctrl'}</kbd> <kbd>Enter</kbd> {t('kbdSubmit')}</span>
            <button type="submit" className="btn primary" disabled={!!disabledReason || busy} aria-describedby="req-why">
              {busy && <span className="spinner sm" />}{busy ? t('submitting') : t('submit')}
            </button>
          </div>
          <p id="req-why" className="why muted small" aria-live="polite">{!busy && disabledReason && !off ? disabledReason : ''}</p>
          {err && <p className="notice err" role="alert">{t('submitFailed')}: {err}</p>}
        </form>
      </header>
      <ol className="how" aria-label="steps">
        {(['1', '2', '3'] as const).map((n) => (
          <li key={n}><span className="n num">{n}</span><div><strong>{t(`wStep${n}` as Key)}</strong><p className="small muted">{t(`wStep${n}d` as Key)}</p></div></li>
        ))}
      </ol>
      <section aria-labelledby="ex-h">
        <h2 id="ex-h" className="sec-h">{t('wExamples')}</h2>
        <div className={'cards' + (prompts.length && examplesOnly.length ? ' mixed' : '')}>
          {examplesOnly.map((c) => (
            <article key={c.key} className={'card example' + (prompts.length >= 2 ? ' tall' : '')}>
              {c.thumb && <a href={`#/run/${c.id}`} className="thumb" tabIndex={-1} aria-hidden="true"><img src={c.thumb} alt="" loading="lazy"
                onError={(e) => { const img = e.currentTarget as HTMLImageElement; if (c.fallback && !img.src.endsWith(c.fallback)) img.src = c.fallback; else img.style.display = 'none'; }} /></a>}
              <div className="card-body">
                <span className={'chip ' + c.tone}>{c.tag}</span>
                <h3><a href={`#/run/${c.id}`}>{c.title}</a></h3>
                <p className="small muted clamp">{c.request}</p>
                <div className="row">
                  <a className="btn sm" href={`#/run/${c.id}`}>{t('openExample')}</a>
                  <button type="button" className="btn sm" disabled={off || busy} title={off ? t('usePromptOff') : undefined} onClick={() => applyPrompt(c.request)}>{t('usePrompt')}</button>
                </div>
              </div>
            </article>
          ))}
          {prompts.map((c) => (
            <article key={c.key} className="card prompt">
              <div className="card-body">
                <span className="chip">{c.tag}</span>
                <h3>{c.title}</h3>
                <p className="small muted clamp">{c.request}</p>
                <div className="row">
                  <button type="button" className="btn sm" disabled={off || busy} title={off ? t('usePromptOff') : undefined} onClick={() => applyPrompt(c.request)}>{t('usePrompt')}</button>
                  {off && <span className="small muted">{t('usePromptOff')}</span>}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
