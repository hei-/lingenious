import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { roundPassed, type LiveState } from '../lib/events';
import type { Round } from '../types';
import { ruleLabels, useI18n } from '../i18n';
import { IssueList } from './Issues';
import { DiffView } from './DiffView';
import { issueId } from '../lib/viewstate';

function RuleNames({ round }: { round: Round }) {
  const { t, lang } = useI18n();
  const rules = [...new Set(round.issues.filter((i) => i.severity === 'error').map((i) => i.rule))];
  const warn = [...new Set(round.issues.filter((i) => i.severity !== 'error').map((i) => i.rule))].filter((r) => !rules.includes(r));
  const all = [...rules.map((r) => [r, true] as const), ...warn.map((r) => [r, false] as const)];
  if (!all.length) return null;
  const shown = all.slice(0, 3);
  return (
    <ul className="rule-names">
      {shown.map(([r, e]) => (
        <li key={r} className={e ? 'e' : 'w'} title={r}>{ruleLabels[lang][r] ?? r} <code>{r}</code></li>
      ))}
      {all.length > 3 && <li className="more">{t('moreRules', { n: all.length - 3 })}</li>}
    </ul>
  );
}

function Step({ state, title, meta, children, className = '' }: { state: 'done' | 'active' | 'fail' | 'pending'; title: ReactNode; meta?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <li className={'step ' + state + (className ? ' ' + className : '')} aria-current={state === 'active' ? 'step' : undefined}>
      <span className="dot" aria-hidden="true">{state === 'active' ? <span className="spinner sm" /> : state === 'done' ? '✓' : state === 'fail' ? '!' : ''}</span>
      <div className="step-body">
        <div className="step-title">{title}{meta && <span className="step-meta">{meta}</span>}</div>
        {children}
      </div>
    </li>
  );
}

export interface TimelineNav {
  selected: number | null; compare: number | null; activeIssue: string | null; lastN: number;
  onSelect: (n: number) => void; onCompare: (n: number) => void; onIssue: (round: number, id: string) => void;
}

function RoundStep({ r, idx, prev, last, onViewFinal, nav, hasNext }: { r: Round; idx: number; prev?: Round; last: boolean; onViewFinal?: () => void; nav?: TimelineNav; hasNext: boolean }) {
  const { t } = useI18n();
  const ok = roundPassed(r);
  const [open, setOpen] = useState(last && !ok);
  const [full, setFull] = useState(false);
  const failedExec = r.exec_ok === false;
  const id = `round-${r.n}`;
  const shown = !!nav && (nav.compare != null ? nav.compare === r.n : nav.selected === r.n || (nav.selected === null && r.n === nav.lastN));
  const toggle = () => {
    if (!open && nav && r.glb) nav.onSelect(r.n); // opening a round also shows its geometry
    setOpen(!open);
  };
  const Chev = open ? ChevronDown : ChevronRight;
  return (
    <Step
      state={ok ? 'done' : 'fail'}
      className={'round' + (shown ? ' shown' : '')}
      title={
        <button type="button" className="round-head" aria-expanded={open} aria-controls={id} onClick={toggle}
          title={nav ? (r.glb ? t('viewRoundGeom') : t('noRoundGeom')) : undefined}>
          <Chev size={14} className="chev" aria-hidden="true" />
          <span className="round-name" title={idx !== r.n ? t('globalRound', { n: r.n }) : undefined}>{t('step_round', { n: idx })}</span>
          <span className={'chip ' + (ok ? 'ok' : 'err')}>{failedExec ? t('execFailed') : ok ? t('passed') : t('failedRound')}</span>
          {r.reconstructed && <span className="badge" title={t('reconstructedTip')}>{t('reconstructed')}</span>}
          {shown && <span className="chip shown-chip">{t('shownIn3d')}</span>}
          <span className="step-meta num">{t('seconds', { s: r.seconds.toFixed(1) })}</span>
        </button>
      }
    >
      {!open && (r.issues.length ? <RuleNames round={r} /> : <p className="muted small round-none">{t('noIssues')}</p>)}
      {nav && !ok && hasNext && r.glb && (
        <button type="button" className="tool cmp" aria-pressed={nav.compare === r.n} onClick={() => nav.onCompare(r.n)}>{nav.compare === r.n ? t('compareOff') : t('compareFix')}</button>
      )}
      {open && (
        <div id={id} className="round-detail">
          {r.issues.length > 0 && <IssueList issues={r.issues} ids={r.issues.map((_, i) => issueId(r.n, i))} activeId={nav?.activeIssue} onFocus={nav ? (id) => nav.onIssue(r.n, id) : undefined} />}
          <div className="round-code">
            <div className="seg" role="group">
              <button type="button" className="tool" aria-pressed={!full} onClick={() => setFull(false)}>{t('codeChanges')}</button>
              <button type="button" className="tool" aria-pressed={full} onClick={() => setFull(true)}>{t('codeFull')}</button>
            </div>
            {r.code ? <DiffView oldText={prev?.code ?? ''} newText={r.code} full={full || !prev?.code} /> : <div className="notice small"><strong>{t('noCode')}</strong><p>{t('noCodeWhy')}</p>{onViewFinal && <button type="button" className="btn" onClick={onViewFinal}>{t('viewFinal')}</button>}</div>}
          </div>
        </div>
      )}
    </Step>
  );
}

export function Timeline({ live, lost, onViewFinal, nav, change, synthetic }: { live: LiveState; lost?: boolean; onViewFinal?: () => void; nav?: TimelineNav; change?: string; synthetic?: boolean }) {
  const { t } = useI18n();
  const { phase } = live;
  const rank = { idle: 0, parsing: 1, spec: 2, generating: 3, fixing: 3, done: 9, error: 9 }[phase];
  if (phase === 'idle') return <div className="empty"><span className="spinner" />{t('waiting')}</div>;
  const finished = phase === 'done' || phase === 'error';
  const lastIdx = live.rounds.length - 1;
  return (
    <div className="timeline">
      {lost && !finished && <div className="notice warn" role="status">{t('connLost')}</div>}
      <ol className="steps">
        {change ? (
          // a modify version edits the previous script: no new requirement parsing / spec
          <Step state={live.rounds.length || finished ? 'done' : 'active'} title={<span className="modify-step">{t('step_modify')}<q>{change}</q></span>} />
        ) : <>
          <Step state={rank > 1 ? 'done' : 'active'} title={t('step_parsing')} />
          {rank >= 2 && <Step state={live.spec ? 'done' : 'active'} title={t('step_spec')} meta={live.spec?.part_type} />}
          {rank >= 3 && <Step state={live.rounds.length || finished ? 'done' : phase === 'generating' ? 'active' : 'done'} title={t('step_generating')} />}
        </>}
        {live.rounds.map((r, i) => (
          <RoundStep key={r.n} r={r} idx={i + 1} prev={live.rounds[i - 1]} last={i === lastIdx && finished} onViewFinal={onViewFinal} nav={nav} hasNext={i < lastIdx} />
        ))}
        {phase === 'generating' && live.rounds.length > 0 && <Step state="active" title={t('step_generating')} />}
        {phase === 'fixing' && <Step state="active" title={t('step_fixing', { n: live.fixing != null && live.rounds.length ? live.fixing - live.rounds[0].n + 1 : live.rounds.length + 1 })} />}
        {phase === 'done' && (
          <Step state={live.status === 'success' ? 'done' : live.status === 'need_info' ? 'pending' : 'fail'} title={live.status === 'success' ? t('done_success') : live.status === 'need_info' ? t('done_need_info') : t('done_failed')}
            meta={synthetic ? <span>{t('syntheticUsage')}</span> : live.usage ? <span className="num">{t('usage', { calls: live.usage.calls ?? 0, p: live.usage.prompt_tokens ?? 0, c: live.usage.completion_tokens ?? 0 })}</span> : undefined} />
        )}
        {phase === 'error' && <Step state="fail" title={t('runError')}><p className="issue-msg">{live.error}</p></Step>}
      </ol>
      {live.status === 'need_info' && !!live.spec?.missing?.length && (
        <div className="notice warn"><strong>{t('missingInfo')}</strong><ul className="plain">{live.spec.missing.map((m, i) => <li key={i}>{m}</li>)}</ul></div>
      )}
      {live.failedArtifacts.map((a) => <div key={a.name} className="notice warn small" role="status">{t('artifactFailed')}: <code>{a.name}</code> {a.message}</div>)}
    </div>
  );
}
