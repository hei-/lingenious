import type { RunSummary } from '../types';
import { fmtDate } from '../lib/util';
import { useI18n, type Key } from '../i18n';

export interface ListState<T> { data: T | null; loading: boolean; error: string | null }

export function StatusDot({ status }: { status: string }) {
  const { t, has } = useI18n();
  const k = `status_${status}`;
  return <span className={'sdot s-' + status} role="img" aria-label={has(k) ? t(k as Key) : status} title={has(k) ? t(k as Key) : status} />;
}

function Item({ r, active, onOpen }: { r: RunSummary; active: boolean; onOpen: (id: string) => void }) {
  const { lang } = useI18n();
  return (
    <li>
      <a href={`#/run/${r.id}`} className={'run-item' + (active ? ' active' : '')} aria-current={active ? 'page' : undefined} onClick={() => onOpen(r.id)}>
        <StatusDot status={r.status} />
        <span className="run-title">{r.title || r.id}</span>
        <span className="run-meta num">{r.versions.length > 1 ? `v${r.versions.length}` : ''} {fmtDate(r.created_at, lang)}</span>
      </a>
    </li>
  );
}

function Section({ title, hint, st, activeId, onOpen, empty, retry }: {
  title: string; hint?: string; st: ListState<RunSummary[]>; activeId: string | null; onOpen: (id: string) => void; empty: string; retry: () => void;
}) {
  const { t } = useI18n();
  return (
    <section className="side-sec" aria-label={title}>
      <h2>{title}{hint && <small>{hint}</small>}</h2>
      {st.loading && !st.data && <p className="muted small"><span className="spinner sm" /> {t('loading')}</p>}
      {st.error && <p className="notice err small">{t('loadFailed')} <button type="button" className="link" onClick={retry}>{t('retry')}</button></p>}
      {st.data && st.data.length === 0 && !st.error && <p className="muted small">{empty}</p>}
      {st.data && st.data.length > 0 && <ul className="run-list">{st.data.map((r) => <Item key={r.id} r={r} active={r.id === activeId} onOpen={onOpen} />)}</ul>}
    </section>
  );
}

interface Props {
  runs: ListState<RunSummary[]>; examples: ListState<RunSummary[]>; activeId: string | null; onOpen: (id: string) => void; reload: () => void;
}
export function Sidebar({ runs, examples, activeId, onOpen, reload }: Props) {
  const { t } = useI18n();
  return (
    <nav className="sidebar-in" aria-label={t('history')}>
      <a href="#/new" className="btn primary block" onClick={() => onOpen('')}>+ {t('newRun')}</a>
      <Section title={t('history')} st={runs} activeId={activeId} onOpen={onOpen} empty={t('noRunsShort')} retry={reload} />
      <Section title={t('examples')} hint={t('examplesHint')} st={examples} activeId={activeId} onOpen={onOpen} empty="—" retry={reload} />
    </nav>
  );
}
