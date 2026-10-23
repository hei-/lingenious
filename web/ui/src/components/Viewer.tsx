import { useEffect, useRef, useState, type ReactNode } from 'react';
import { SceneController, type Dims, type MarkerSpec, type Placeholder } from '../lib/scene';
import { useI18n } from '../i18n';

interface Props {
  url: string | null; fallbackDims: Dims; compact?: boolean; label?: string;
  placeholder?: Placeholder; ghostUrl?: string | null;
  markers?: MarkerSpec[]; activeId?: string | null; onMarkerClick?: (id: string) => void;
  /** extra toolbar content (e.g. a STEP download) */
  extra?: ReactNode;
}

function webglOk() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}

export function Viewer({ url, fallbackDims, compact, label, placeholder = 'box', ghostUrl = null, markers, activeId = null, onMarkerClick, extra }: Props) {
  const { t } = useI18n();
  const host = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const ctl = useRef<SceneController | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'fallback' | 'nogl'>('loading');
  const [dims, setDims] = useState<Dims>(fallbackDims);
  const [on, setOn] = useState({ wire: false, edges: true, ortho: false, axes: true, dims: true });
  const fb = `${fallbackDims.x}/${fallbackDims.y}/${fallbackDims.z}`;

  useEffect(() => {
    if (!host.current || !overlay.current) return;
    if (!webglOk()) { setState('nogl'); return; }
    const c = new SceneController(host.current, overlay.current);
    ctl.current = c;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onTheme = () => c.refreshPalette();
    mq.addEventListener('change', onTheme);
    const mo = new MutationObserver(onTheme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => { mq.removeEventListener('change', onTheme); mo.disconnect(); c.dispose(); ctl.current = null; };
  }, []);

  useEffect(() => {
    const c = ctl.current;
    if (!c) return;
    let live = true;
    setState('loading');
    c.load(url, fallbackDims, placeholder).then((r) => {
      if (!live) return;
      setDims(r.dims); setState(r.fallback ? 'fallback' : 'ready');
      (Object.keys(on) as (keyof typeof on)[]).forEach((k) => c.setFlag(k, on[k]));
    });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, fb]);

  useEffect(() => { ctl.current?.loadGhost(ghostUrl, fallbackDims, placeholder); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [ghostUrl, fb]);
  const cb = useRef(onMarkerClick);
  cb.current = onMarkerClick;
  useEffect(() => { ctl.current?.setMarkers(markers ?? [], (id) => cb.current?.(id)); }, [markers]);
  useEffect(() => {
    ctl.current?.setHighlight(activeId);
    if (activeId && (state === 'ready' || state === 'fallback')) ctl.current?.focusMarker(activeId);
  }, [activeId, state, markers]);

  const toggle = (k: keyof typeof on) => {
    const v = !on[k];
    setOn({ ...on, [k]: v });
    ctl.current?.setFlag(k, v);
  };
  const btn = (k: keyof typeof on, text: string, pressed = on[k]) => (
    <button type="button" className="tool" aria-pressed={pressed} onClick={() => toggle(k)}>{text}</button>
  );
  const f = (n: number) => n.toFixed(1);

  return (
    <div className={'viewer' + (compact ? ' compact' : '')} role="group" aria-label={label ?? t('viewerLabel')}>
      <div className="viewer-bar">
        <button type="button" className="tool" onClick={() => ctl.current?.fit()}>{t('v_fit')}</button>
        {btn('wire', t('v_wire'))}
        {btn('edges', t('v_edges'))}
        {btn('ortho', on.ortho ? t('v_ortho') : t('v_persp'))}
        {btn('axes', t('v_axes'))}
        {btn('dims', t('v_dims'))}
        {extra && <><span className="spacer" />{extra}</>}
      </div>
      <div className="viewer-stage" ref={host} tabIndex={0} aria-label={t('v_hint')}>
        <div className="dim-layer" ref={overlay} aria-hidden="true" />
        {state === 'loading' && <div className="viewer-msg"><span className="spinner" />{t('v_loading')}</div>}
        {state === 'nogl' && <div className="viewer-msg err">{t('v_noWebgl')}</div>}
      </div>
      <div className="viewer-foot">
        <span className="num dimsum">{f(dims.x)} × {f(dims.y)} × {f(dims.z)} mm</span>
        {state === 'fallback' && <span className="badge warn">{t('v_fallback')}</span>}
        <span className="muted hint-text">{t('v_hint')}</span>
      </div>
    </div>
  );
}
