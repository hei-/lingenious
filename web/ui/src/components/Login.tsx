import { useState } from 'react';
import { auth } from '../api';
import { useI18n } from '../i18n';

export function Login({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [token, setToken] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || busy) return;
    setBusy(true); setErr(null);
    try { await auth.login(token); setToken(''); onDone(); }
    catch (x) { setErr((x as { status?: number }).status === 429 ? t('loginWait') : t('loginBad')); }
    finally { setBusy(false); }
  };
  return (
    <form className="login" onSubmit={submit}>
      <h1>{t('loginTitle')}</h1>
      <p>{t('loginHint')}</p>
      <label htmlFor="tok">{t('loginToken')}</label>
      <input id="tok" type="password" autoComplete="current-password" autoFocus value={token} onChange={(e) => setToken(e.target.value)} aria-invalid={!!err} />
      {err && <div className="err" role="alert">{err}</div>}
      <button type="submit" className="btn primary" disabled={!token || busy}>{t('loginSubmit')}</button>
    </form>
  );
}
