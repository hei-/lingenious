import type { Issue, PartSpec, RunJson } from '../types';
import { useI18n, type Key } from '../i18n';
import { IssueList } from './Issues';
import { issueId } from '../lib/viewstate';

export function ReportPanel({ run, onFocus, activeId }: { run: RunJson | null; onFocus?: (id: string) => void; activeId?: string | null }) {
  const { t } = useI18n();
  if (!run) return <div className="empty">{t('reportEmpty')}</div>;
  const issues: Issue[] = run.final_issues ?? run.rounds[run.rounds.length - 1]?.issues ?? [];
  const lastN = run.rounds?.length ? run.rounds[run.rounds.length - 1].n : 1;
  const levels = ['L0', 'L1', 'L2', 'L3'] as const;
  const ok = !issues.some((i) => i.severity === 'error');
  return (
    <div className="report">
      <div className={'notice ' + (issues.length === 0 ? 'ok' : ok ? 'warn' : 'err')} role="status">
        {issues.length === 0 ? t('allPass') : `${t('unresolved')}: ${issues.length}`}
      </div>
      {levels.map((lv) => {
        const idx = issues.map((_, i) => i).filter((i) => issues[i].level === lv);
        const list = idx.map((i) => issues[i]);
        if (lv === 'L0' && !list.length) return null;
        const errs = list.filter((i) => i.severity === 'error').length;
        return (
          <section key={lv} className="level">
            <h3>
              {t(`level_${lv}` as Key)}
              <span className={'chip ' + (errs ? 'err' : list.length ? 'warn' : 'ok')}>{list.length === 0 ? t('passed') : <span className="num">{list.length}</span>}</span>
            </h3>
            {list.length > 0 && <IssueList issues={list} ids={idx.map((i) => issueId(lastN, i))} activeId={activeId} onFocus={onFocus} />}
          </section>
        );
      })}
    </div>
  );
}

function Dl({ rows }: { rows: [string, React.ReactNode][] }) {
  return <dl className="kv">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>)}</dl>;
}

export function SpecPanel({ spec }: { spec?: PartSpec }) {
  const { t } = useI18n();
  if (!spec) return <div className="empty">{t('specEmpty')}</div>;
  const a = spec.assertions ?? {};
  const bb = a.bbox;
  const rows: [string, React.ReactNode][] = [];
  if (spec.part_type) rows.push([t('partType'), spec.part_type]);
  if (spec.material) rows.push([t('material'), spec.material]);
  if (spec.process) rows.push([t('process'), spec.process]);
  if (bb) rows.push([t('bbox'), `${bb.x} × ${bb.y} × ${bb.z} mm${bb.tol != null ? ` (±${bb.tol})` : ''}`]);
  if (a.hole_count != null) rows.push([t('holeCount'), String(a.hole_count)]);
  if (Array.isArray(a.hole_diameters)) rows.push([t('holeDiameters'), (a.hole_diameters as number[]).join(', ') + (a.diameter_tol != null ? ` (±${a.diameter_tol})` : '')]);
  return (
    <div className="spec">
      <Dl rows={rows} />
      {!!spec.features?.length && (
        <>
          <h3>{t('features')}</h3>
          <div className="table-scroll">
            <table className="tbl">
              <tbody>
                {spec.features.map((f) => (
                  <tr key={f.id}>
                    <th scope="row">{f.type}<code>{f.id}</code></th>
                    <td className="num">{Object.entries(f.dims).map(([k, v]) => `${k} ${v}`).join(' · ')}</td>
                    <td className="muted">{f.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {!!spec.defaults_used?.length && (<><h3>{t('defaults')}</h3><ul className="plain">{spec.defaults_used.map((d, i) => <li key={i}>{d}</li>)}</ul></>)}
      {!!spec.missing?.length && (<><h3>{t('missing')}</h3><ul className="plain">{spec.missing.map((d, i) => <li key={i}>{d}</li>)}</ul></>)}
    </div>
  );
}
