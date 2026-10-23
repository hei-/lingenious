import { useEffect, useMemo, useReducer, useState } from 'react';
import { api, isMock, type StreamStatus } from '../api';
import { initialLive, liveFromRunJson, reduceEvent, type LiveState } from '../lib/events';
import type { Health, LiveEvent, RunDetail } from '../types';
import { bboxDims } from '../lib/util';
import { ruleLabels, useI18n, type Key } from '../i18n';
import { Timeline, type TimelineNav } from './Timeline';
import { geometryPlan, initialView, issueId, viewReducer } from '../lib/viewstate';
import type { MarkerSpec } from '../lib/scene';
import { Viewer } from './LazyViewer';
import { ReportPanel, SpecPanel } from './Report';
import { DrawingView } from './Drawing';
import { ModifyBox } from './ModifyBox';
import { Compare } from './Compare';
import { CodeView } from './DiffView';
import { StatusDot } from './Sidebar';
import { fetchText } from '../api';
import { Check, Copy, Download, Info, Lock } from 'lucide-react';
import { DownloadMenu } from './Downloads';
import { downloadName, fileState, type FileCtx } from '../lib/files';

type Tab = 'model' | 'report' | 'drawing' | 'code' | 'compare';
const TABS: Tab[] = ['model', 'report', 'drawing', 'code', 'compare'];

function liveReducer(s: LiveState, a: LiveEvent | { type: 'reset' }): LiveState {
  return a.type === 'reset' ? initialLive : reduceEvent(s, a);
}

function useCode(url: string | null) {
  const [st, setSt] = useState<{ text: string | null; err: boolean }>({ text: null, err: false });
  useEffect(() => {
    if (!url) { setSt({ text: null, err: false }); return; }
    let live = true;
    setSt({ text: null, err: false });
    fetchText(url).then((text) => live && setSt({ text, err: false })).catch(() => live && setSt({ text: null, err: true }));
    return () => { live = false; };
  }, [url]);
  return st;
}

interface Props { detail: RunDetail; version: number; health: Health | null; onVersion: (v: number) => void; refresh: () => Promise<void>; onChanged: () => void }

export function Workspace({ detail, version, health, onVersion, refresh, onChanged }: Props) {
  const { t, has: hasKey, lang } = useI18n();
  const [view, dispatchView] = useReducer(viewReducer, initialView);
  useEffect(() => { dispatchView({ type: 'reset' }); }, [detail.id, version]);
  const [tab, setTab] = useState<Tab>('model');
  const info = detail.versions.find((v) => v.version === version);
  const run = info?.run ?? null;
  const [liveState, dispatch] = useReducer(liveReducer, initialLive);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    if (run) return;
    dispatch({ type: 'reset' }); setLost(false);
    const unsub = api.subscribe(detail.id, version, (e) => {
      dispatch(e);
      if (e.type === 'done' || e.type === 'error') { void refresh(); onChanged(); }
    }, (s: StreamStatus) => setLost(s === 'lost'));
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id, version, !!run]);

  const live = useMemo(() => (run ? liveFromRunJson(run) : liveState), [run, liveState]);
  const finished = !!run;
  const has = (f: string) => !!info && finished && info.files.includes(f);
  const url = (f: string) => api.fileUrl(detail.id, version, f);
  const codeUrl = finished ? url('part.py') : null;
  const code = useCode(tab === 'code' ? codeUrl : null);
  const spec = run?.spec ?? live.spec;
  const running = !finished && live.phase !== 'error';

  const has2 = (st: string) => (hasKey(`status_${st}`) ? t(`status_${st}` as Key) : st);
  const rounds = useMemo(() => run?.rounds ?? [], [run]);
  const lastN = rounds.length ? rounds[rounds.length - 1].n : 1;
  const plan = useMemo(() => geometryPlan(view, rounds), [view, rounds]);
  const roundGlb = (n: number | null) => { const g = n == null ? undefined : rounds.find((r) => r.n === n)?.glb; return g ? url(g) : null; };
  const mainUrl = plan.mainRound != null ? roundGlb(plan.mainRound) : has('part.glb') ? url('part.glb') : null;
  const ghostUrl = plan.ghostRound != null ? roundGlb(plan.ghostRound) : null;
  const markers = useMemo<MarkerSpec[]>(() => {
    const list = plan.markersRound === lastN && run?.final_issues ? run.final_issues : rounds.find((r) => r.n === plan.markersRound)?.issues ?? [];
    return list.flatMap((i, k) => i.location ? [{ id: issueId(plan.markersRound, k), locs: [i.location, ...(i.location2 ? [i.location2] : [])], severity: i.severity, label: ruleLabels[lang][i.rule] ?? i.rule }] : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan.markersRound, run, lang]);
  const focusIssue = (id: string, round: number | null) => { dispatchView({ type: 'issue', id, round }); setTab('model');
    window.setTimeout(() => document.getElementById('panel-model')?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }), 60);
  };
  const nav: TimelineNav | undefined = finished ? {
    selected: view.round, compare: view.compare, activeIssue: view.issue, lastN,
    onSelect: (n) => { dispatchView({ type: 'round', n: n === lastN ? null : n }); setTab('model'); },
    onCompare: (n) => { dispatchView({ type: 'compare', n }); setTab('model'); },
    onIssue: (n, id) => focusIssue(id, n === lastN ? null : n),
  } : undefined;
  const chipRound = rounds.find((r) => r.n === plan.chipRound);
  const localN = (n: number) => rounds.findIndex((r) => r.n === n) + 1 || n; // rounds are numbered within the version in the UI
  const modifyOff = detail.readOnly ? t('modifyOff') : health && !health.llm_configured ? t('modifyNoLlm')
    : detail.versions.some((v) => !v.run) ? t('modifyBusy') : null;

  const fctx: FileCtx = { files: info?.files ?? [], artifacts: liveState.artifacts, failed: live.failedArtifacts.length ? live.failedArtifacts : liveState.failedArtifacts, running };
  const dl = (f: string) => api.downloadUrl(detail.id, version, f);
  const dname = (f: string) => downloadName(detail.title || detail.id, version, f);
  const step = fileState('part.step', fctx);

  const onTabKey = (e: React.KeyboardEvent) => {
    const i = TABS.indexOf(tab);
    if (e.key === 'ArrowRight') setTab(TABS[(i + 1) % TABS.length]);
    else if (e.key === 'ArrowLeft') setTab(TABS[(i + TABS.length - 1) % TABS.length]);
    else return;
    e.preventDefault();
    requestAnimationFrame(() => document.getElementById(`tab-${TABS[(e.key === 'ArrowRight' ? i + 1 : i + TABS.length - 1) % TABS.length]}`)?.focus());
  };

  return (
    <div className="page">
      <header className="ws-head">
        <div className="ws-title">
          <StatusDot status={run ? run.status : live.phase === 'error' ? 'error' : 'running'} />
          <h1 title={detail.request}>{detail.title || detail.id}</h1>
          {detail.readOnly && <span className="badge">{t('readOnly')}</span>}
          {info?.synthetic && <span className="badge syn-badge" title={`${t('syntheticTip')} ${info.synthetic}`}>✎ {t('synthetic')}</span>}
        </div>
        {detail.versions.length <= 1 ? (
          <span className="vpill num" title={t('version')}>v{detail.versions[0]?.version ?? version}</span>
        ) : (
          <div className="vsw" role="tablist" aria-label={t('version')}>
            {detail.versions.map((v) => {
              const st = v.status ?? (v.run ? v.run.status : 'running');
              const tip = [`v${v.version} · ${t('versionStatus')}: ${has2(st)}`, v.change, v.synthetic && `${t('synthetic')}: ${t('syntheticTip')}`].filter(Boolean).join('\n');
              return (
                <button key={v.version} type="button" role="tab" aria-selected={v.version === version} className="vtab num" title={tip} aria-label={tip.replace('\n', ' — ')} onClick={() => onVersion(v.version)}>
                  <span className={'sdot s-' + st} aria-hidden="true" />v{v.version}{v.synthetic && <span className="syn" aria-hidden="true">✎</span>}
                </button>
              );
            })}
          </div>
        )}
        <DownloadMenu title={detail.title || detail.id} version={version} ctx={fctx} sizes={info?.sizes} synthetic={info?.synthetic}
          notPassed={!!run && run.status !== 'success'} href={dl} zip={api.bundleUrl(detail.id, version)} />
      </header>
      <p className="req">{detail.request}</p>
      {detail.selection && (() => {
        const sel = detail.selection;
        const tip = sel.summary.map((r, i) => `${t('selRun', { n: i + 1 })}${i === sel.picked ? ' ' + t('selPickedMark') : ''}: ` +
          Object.entries(r).map(([v, [st, n]]) => `v${v} ${has2(st)} · ${t('selRounds', { n })}`).join(', ')).join('\n');
        return <p className="sel-line muted small" title={tip}><Info size={13} aria-hidden="true" />{t('selPicked', { runs: sel.runs, n: sel.picked + 1 })}{sel.reason ? ` · ${(lang === 'zh' && sel.reason_zh) || sel.reason}` : ''}</p>;
      })()}
      {info?.change && <p className="req change"><span className="badge">v{version}</span> {info.change}</p>}

      <div className="ws-grid">
        <aside className="ws-left" aria-label={t('timeline')}>
          <div className="tl-card">
            <h2 className="tl-head">{t('timeline')}</h2>
            {!info && !live.rounds.length && live.phase === 'idle' ? <div className="empty"><span className="spinner" />{t('waiting')}</div> : <Timeline live={live} lost={lost} nav={nav} change={info?.change} synthetic={!!info?.synthetic} onViewFinal={finished ? () => setTab('code') : undefined} />}
          </div>
          {detail.readOnly
            ? <p className="ro-line muted small"><Lock size={13} aria-hidden="true" />{t('roReadonly')} · <a href="#/new">{t('roNew')}</a></p>
            : <ModifyBox disabledReason={modifyOff} onSubmit={async (change) => {
              const r = await api.modify(detail.id, change);
              await refresh(); onChanged(); onVersion(r.version); setTab('model');
            }} />}

        </aside>

        <section className="ws-main">
          <div className="tabs" role="tablist" onKeyDown={onTabKey}>
            {TABS.map((k) => (
              <button key={k} id={`tab-${k}`} role="tab" type="button" aria-selected={tab === k} aria-controls={`panel-${k}`} tabIndex={tab === k ? 0 : -1} className="tab" onClick={() => setTab(k)}>
                {t(`tabs_${k}` as Key)}
              </button>
            ))}
          </div>
          <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="panel">
            {tab === 'model' && (
              finished
                ? <>
                  {(chipRound || plan.ghostRound != null) && (
                    <div className="geom-chip" role="status">
                      {chipRound && <><strong>{t('geomRound', { n: localN(chipRound.n) })}</strong>{chipRound.reconstructed && <span className="badge" title={t('reconstructedTip')}>{t('reconstructed')}</span>}</>}
                      {plan.ghostRound != null && <span>{t('compareLegend', { a: localN(plan.ghostRound), b: plan.mainRound == null ? t('finalGeom') : t('step_round', { n: localN(plan.mainRound) }) })}</span>}
                      <button type="button" className="tool" onClick={() => dispatchView({ type: 'round', n: null })}>{t('backFinal')}</button>
                    </div>
                  )}
                  <Viewer url={mainUrl} ghostUrl={ghostUrl} fallbackDims={bboxDims(spec)} placeholder={isMock() ? 'bracket' : 'box'}
                    markers={markers} activeId={view.issue} onMarkerClick={(id) => dispatchView({ type: 'issue', id })}
                    extra={step.state === 'ready' ? <a className="tool" href={dl('part.step')} download={dname('part.step')}><Download size={14} aria-hidden="true" />{t('dl_step_short')}</a> : null} />
                </>
                : <div className="empty tall">{running ? <><span className="spinner" />{t('v_loading')}</> : t('reportEmpty')}</div>
            )}
            {tab === 'report' && (
              <div className="two-col">
                <div><ReportPanel onFocus={(id) => focusIssue(id, null)} activeId={view.issue} run={run ?? (live.rounds.length ? { status: live.status ?? 'running', rounds: live.rounds, final_issues: live.rounds[live.rounds.length - 1].issues } : null)} /></div>
                <div><h2 className="sec-h">{t('spec')}</h2><SpecPanel spec={spec} /></div>
              </div>
            )}
            {tab === 'drawing' && (finished && has('drawing.png') ? <DrawingView src={url('drawing.png')} pdf={has('drawing.pdf') ? { href: dl('drawing.pdf'), name: dname('drawing.pdf') } : null} dxf={has('drawing.dxf') ? { href: dl('drawing.dxf'), name: dname('drawing.dxf') } : null} /> : <div className="empty tall">{running ? <span className="spinner" /> : t('drawingEmpty')}</div>)}
            {tab === 'code' && (
              code.err ? <div className="empty">{t('noCode')}</div> : code.text === null ? <div className="empty"><span className="spinner" />{t('loadingCode')}</div> : <><CodeTools text={code.text} href={dl('part.py')} name={dname('part.py')} /><CodeView text={code.text} /></>
            )}
            {tab === 'compare' && <Compare detail={detail} current={version} />}
          </div>
        </section>
      </div>
    </div>
  );
}

function CodeTools({ text, href, name }: { text: string; href: string; name: string }) {
  const { t } = useI18n();
  const [st, setSt] = useState<'idle' | 'ok' | 'err'>('idle');
  useEffect(() => { if (st === 'idle') return; const h = window.setTimeout(() => setSt('idle'), 1800); return () => window.clearTimeout(h); }, [st]);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setSt('ok'); } catch { setSt('err'); }
  };
  return (
    <div className="viewer-bar code-tools">
      <button type="button" className="tool" onClick={copy} aria-live="polite">
        {st === 'ok' ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
        {st === 'ok' ? t('copied') : st === 'err' ? t('copyFailed') : t('copy')}
      </button>
      <a className="tool" href={href} download={name}><Download size={14} aria-hidden="true" />{t('dl_py_btn')}</a>
      <span className="muted small dl-fname">{name}</span>
    </div>
  );
}
