import { useState } from 'react';
import { useI18n } from '../i18n';

interface Props { disabledReason: string | null; onSubmit: (change: string) => Promise<void> }

export function ModifyBox({ disabledReason, onSubmit }: Props) {
  const { t, errMsg } = useI18n();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy || disabledReason) return;
    setBusy(true); setErr(null);
    try { await onSubmit(text.trim()); setText(''); } catch (x) { setErr(errMsg(x)); } finally { setBusy(false); }
  };
  return (
    <form className="modify" onSubmit={submit}>
      <label htmlFor="modify-in" className="label">{t('modifyTitle')}</label>
      <div className="row">
        <input id="modify-in" type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('modifyPlaceholder')} disabled={!!disabledReason || busy} maxLength={500} />
        <button type="submit" className="btn primary" disabled={!!disabledReason || busy || !text.trim()}>{busy ? <span className="spinner sm" /> : null}{t('modifySubmit')}</button>
      </div>
      {disabledReason && <p className="muted small">{disabledReason}</p>}
      {err && <p className="notice err" role="alert">{t('modifyFailed')}: {err}</p>}
    </form>
  );
}
