import { useMemo } from 'react';
import { collapseContext, diffLines, diffStats } from '../lib/diff';
import { useI18n } from '../i18n';

export function DiffView({ oldText, newText, full }: { oldText: string; newText: string; full?: boolean }) {
  const { t } = useI18n();
  const ops = useMemo(() => diffLines(oldText, newText), [oldText, newText]);
  const stats = diffStats(ops);
  const rows = useMemo(() => (full ? ops : collapseContext(ops, 3)), [ops, full]);
  const same = stats.add === 0 && stats.del === 0;
  return (
    <div className="diff">
      <div className="diff-head num">
        {same ? <span className="muted">{t('diffNone')}</span> : <><span className="add-t">+{stats.add}</span> <span className="del-t">−{stats.del}</span></>}
      </div>
      <div className="code-scroll" tabIndex={0} role="region" aria-label="diff">
        <table className="code">
          <tbody>
            {rows.map((r, i) =>
              r.type === 'gap' ? (
                <tr key={i} className="gap"><td colSpan={4}>{t('diffGap', { n: r.count })}</td></tr>
              ) : (
                <tr key={i} className={r.type}>
                  <td className="ln num">{r.a ?? ''}</td>
                  <td className="ln num">{r.b ?? ''}</td>
                  <td className="sign" aria-hidden="true">{r.type === 'add' ? '+' : r.type === 'del' ? '−' : ''}</td>
                  <td className="src">{r.text || ' '}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CodeView({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  return (
    <div className="code-scroll" tabIndex={0} role="region" aria-label="code">
      <table className="code">
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}><td className="ln num">{i + 1}</td><td className="src">{l || ' '}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
