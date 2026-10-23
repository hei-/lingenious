import { useCallback, useEffect, useState } from 'react';
import { Languages, Menu, Moon, Sun, SunMoon } from 'lucide-react';
import { api, auth, enableMock, isMock, setUnauthorizedHandler } from './api';
import type { Health, RunDetail, RunSummary } from './types';
import { useI18n } from './i18n';
import { Sidebar, type ListState } from './components/Sidebar';
import { NewRun } from './components/NewRun';
import { Workspace } from './components/Workspace';
import { Login } from './components/Login';

type Route = { name: 'new' } | { name: 'run'; id: string; version: number | null };

function parseHash(): Route {
  const m = location.hash.match(/^#\/run\/([^/]+)(?:\/v(\d+))?/);
  return m ? { name: 'run', id: decodeURIComponent(m[1]), version: m[2] ? Number(m[2]) : null } : { name: 'new' };
}

function useRoute() {
  const [r, setR] = useState<Route>(parseHash);
  useEffect(() => { const f = () => setR(parseHash()); window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f); }, []);
  return r;
}

const initList: ListState<RunSummary[]> = { data: null, loading: true, error: null };

export default function App() {
  const { t, lang, setLang, errMsg } = useI18n();
  const [theme, setTheme] = useState<'system' | 'light' | 'dark'>(() => { try { const v = localStorage.getItem('theme'); return v === 'light' || v === 'dark' ? v : 'system'; } catch { return 'system'; } });
  useEffect(() => {
    const el = document.documentElement;
    if (theme === 'system') el.removeAttribute('data-theme'); else el.setAttribute('data-theme', theme);
    try { localStorage.setItem('theme', theme); } catch { /* ignore */ }
  }, [theme]);
  const route = useRoute();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [mock, setMock] = useState(isMock());
  const [runs, setRuns] = useState(initList);
  const [examples, setExamples] = useState(initList);
  const [drawer, setDrawer] = useState(false);

  const loadLists = useCallback(() => {
    api.listRuns().then((data) => setRuns({ data, loading: false, error: null })).catch((e) => setRuns((s) => ({ ...s, loading: false, error: String(e.message) })));
    api.listExamples().then((data) => setExamples({ data, loading: false, error: null })).catch((e) => setExamples((s) => ({ ...s, loading: false, error: String(e.message) })));
  }, []);

  // any 401 (expired/missing token) drops back to the login screen
  useEffect(() => {
    setUnauthorizedHandler(() => setHealth((h) => (h && h.auth_required ? { ...h, authenticated: false } : h)));
    return () => setUnauthorizedHandler(null);
  }, []);
  const [session, setSession] = useState(0); // bumped after login to reload everything

  useEffect(() => {
    let live = true;
    (async () => {
      try { const h = await api.health(); if (live) setHealth(h); }
      catch {
        if (import.meta.env.DEV && !isMock()) {
          enableMock(); setMock(true);
          const h = await api.health(); if (live) setHealth(h);
        }
      }
      if (live) { setHealthLoading(false); loadLists(); }
    })();
    return () => { live = false; };
  }, [loadLists, session]);

  useEffect(() => { setDrawer(false); }, [route]);

  // detail of the open run
  const runId = route.name === 'run' ? route.id : null;
  const [detail, setDetail] = useState<{ id: string; data: RunDetail | null; error: string | null; status?: number } | null>(null);
  const loadDetail = useCallback(async () => {
    if (!runId) return;
    try { const d = await api.getRun(runId); setDetail({ id: runId, data: d, error: null }); }
    catch (e) { setDetail((s) => (s?.id === runId && s.data ? s : { id: runId, data: null, error: errMsg(e), status: (e as { status?: number }).status })); }
  }, [runId]);
  useEffect(() => { setDetail(null); if (runId && !healthLoading) void loadDetail(); }, [runId, healthLoading, loadDetail]);

  const goVersion = (id: string, v: number) => { location.hash = `#/run/${encodeURIComponent(id)}/v${v}`; };

  const create = async (b: { request: string; material: string; process: string }) => {
    const { id } = await api.createRun(b);
    loadLists();
    location.hash = `#/run/${encodeURIComponent(id)}/v1`;
  };

  let main;
  if (route.name === 'new') main = <NewRun health={health} healthLoading={healthLoading} onCreate={create} firstExample={examples.data?.[0]?.id ?? null} examples={examples.data} />;
  else if (!detail || detail.id !== route.id) main = <div className="page"><div className="empty tall"><span className="spinner" />{t('loading')}</div></div>;
  else if (!detail.data) main = (
    <div className="page"><div className="empty tall">
      <p>{detail.status === 404 ? t('notFound') : `${t('loadFailed')}: ${detail.error}`}</p>
      <div className="row"><button type="button" className="btn" onClick={() => void loadDetail()}>{t('retry')}</button><a className="btn" href="#/new">{t('backHome')}</a></div>
    </div></div>
  );
  else {
    const d = detail.data;
    const version = route.version ?? d.versions[d.versions.length - 1]?.version ?? 1;
    main = <Workspace key={d.id} detail={d} version={version} health={health} onVersion={(v) => goVersion(d.id, v)} refresh={loadDetail} onChanged={loadLists} />;
  }

  const locked = !!health?.auth_required && !health.authenticated;
  const logout = async () => { try { await auth.logout(); } catch { /* ignore */ } setRuns(initList); setExamples(initList); setDetail(null); setHealth((h) => (h ? { ...h, authenticated: false } : h)); };

  return (
    <div className="app">
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <button type="button" className="icon-btn menu-btn" aria-label={t('menu')} aria-expanded={drawer} onClick={() => setDrawer(!drawer)}><Menu size={18} aria-hidden /></button>
        <a href="#/new" className="brand"><span className="logo" aria-hidden="true" />{t('appName')}<span className="tag">{t('tagline')}</span></a>
        <span className="spacer" />
        <button type="button" className="tool icon" onClick={() => setTheme(theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system')} title={t(theme === 'system' ? 'themeAuto' : theme === 'light' ? 'themeLight' : 'themeDark')} aria-label={t(theme === 'system' ? 'themeAuto' : theme === 'light' ? 'themeLight' : 'themeDark')}>{theme === 'system' ? <SunMoon size={15} aria-hidden /> : theme === 'light' ? <Sun size={15} aria-hidden /> : <Moon size={15} aria-hidden />}</button>
        <button type="button" className="tool lang-btn" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')} lang={lang === 'zh' ? 'en' : 'zh-CN'} title={t('languageSwitch')} aria-label={t('languageSwitch')}><Languages size={15} aria-hidden /><span className="lang-code">{t('language')}</span></button>
        {health?.auth_required && health.authenticated && <button type="button" className="tool" onClick={() => void logout()}>{t('logout')}</button>}
      </header>
      {mock && <div className="banner" role="status">{t('mockBanner')}</div>}
      {locked ? <main id="main" className="main"><Login onDone={() => { setHealthLoading(true); setSession((n) => n + 1); }} /></main> :
      <div className={'shell' + (drawer ? ' drawer-open' : '')}>
        <aside className="sidebar">
          <Sidebar runs={runs} examples={examples} activeId={runId} onOpen={() => setDrawer(false)} reload={loadLists} />
        </aside>
        {drawer && <button type="button" className="scrim" aria-label={t('close')} onClick={() => setDrawer(false)} />}
        <main id="main" className="main" tabIndex={-1}>{main}</main>
      </div>}
    </div>
  );
}
