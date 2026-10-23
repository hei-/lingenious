import type { Issue } from '../types';
import { ruleLabels, useI18n } from '../i18n';

export function SevChip({ sev }: { sev: Issue['severity'] }) {
  const { t } = useI18n();
  return <span className={'chip ' + (sev === 'error' ? 'err' : 'warn')}>{sev === 'error' ? t('sev_error') : t('sev_warning')}</span>;
}

const fmt = (v: unknown) => (typeof v === 'number' ? String(Math.round(v * 1000) / 1000) : v == null ? '—' : String(v));

interface ItemProps { issue: Issue; id?: string; active?: boolean; onFocus?: (id: string) => void }

export function IssueItem({ issue, id, active, onFocus }: ItemProps) {
  const { t, lang } = useI18n();
  const name = ruleLabels[lang][issue.rule] ?? issue.rule;
  const canFocus = !!(issue.location && id && onFocus);
  return (
    <li className={'issue' + (canFocus ? ' locatable' : '') + (active ? ' active' : '')} onClick={canFocus ? () => onFocus!(id!) : undefined}>
      <div className="issue-head">
        <span className="chip lvl">{issue.level}</span>
        <SevChip sev={issue.severity} />
        <strong className="rule">{name}</strong>
        <code className="rule-id">{issue.rule}</code>
        {canFocus && (
          <button type="button" className="tool locate" aria-pressed={!!active} title={t('locate')} onClick={(e) => { e.stopPropagation(); onFocus!(id!); }}>◎ {t('locate')}</button>
        )}
      </div>
      <p className="issue-msg">{issue.message}</p>
      {(issue.measured != null || issue.required != null) && (
        <dl className="mr num">
          <div><dt>{t('measured')}</dt><dd>{fmt(issue.measured)}</dd></div>
          <div><dt>{t('required')}</dt><dd>{fmt(issue.required)}</dd></div>
          {issue.target && <div><dt>{t('target')}</dt><dd>{issue.target}</dd></div>}
        </dl>
      )}
      {issue.hint && <p className="issue-hint"><span>{t('hint')}</span> {issue.hint}</p>}
    </li>
  );
}

interface ListProps { issues: Issue[]; ids?: string[]; activeId?: string | null; onFocus?: (id: string) => void }
export function IssueList({ issues, ids, activeId, onFocus }: ListProps) {
  return <ul className="issues">{issues.map((i, k) => <IssueItem key={k} issue={i} id={ids?.[k]} active={!!ids && ids[k] === activeId} onFocus={onFocus} />)}</ul>;
}
