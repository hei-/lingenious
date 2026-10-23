import { useRef, useState } from 'react';
import { useI18n } from '../i18n';
import { Download, Minus, Plus, RotateCcw } from 'lucide-react';

type Dl = { href: string; name: string } | null;

export function DrawingView({ src, pdf, dxf }: { src: string; pdf: Dl; dxf: Dl }) {
  const { t } = useI18n();
  const [z, setZ] = useState(1);
  const [p, setP] = useState({ x: 0, y: 0 });
  const [err, setErr] = useState(false);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const clamp = (v: number) => Math.min(8, Math.max(0.5, v));
  const reset = () => { setZ(1); setP({ x: 0, y: 0 }); };
  const onKey = (e: React.KeyboardEvent) => {
    const step = 40;
    if (e.key === '+' || e.key === '=') setZ((v) => clamp(v * 1.25));
    else if (e.key === '-') setZ((v) => clamp(v / 1.25));
    else if (e.key === '0') reset();
    else if (e.key === 'ArrowLeft') setP((q) => ({ ...q, x: q.x + step }));
    else if (e.key === 'ArrowRight') setP((q) => ({ ...q, x: q.x - step }));
    else if (e.key === 'ArrowUp') setP((q) => ({ ...q, y: q.y + step }));
    else if (e.key === 'ArrowDown') setP((q) => ({ ...q, y: q.y - step }));
    else return;
    e.preventDefault();
  };
  if (err) return <div className="empty">{t('drawingEmpty')}</div>;
  return (
    <div className="drawing">
      <div className="viewer-bar">
        <button type="button" className="tool" onClick={() => setZ((v) => clamp(v * 1.25))} aria-label={t('zoomIn')} title={t('zoomIn')}><Plus size={14} aria-hidden="true" /></button>
        <button type="button" className="tool" onClick={() => setZ((v) => clamp(v / 1.25))} aria-label={t('zoomOut')} title={t('zoomOut')}><Minus size={14} aria-hidden="true" /></button>
        <button type="button" className="tool" onClick={reset}><RotateCcw size={14} aria-hidden="true" />{t('reset')}</button>
        <span className="num muted">{Math.round(z * 100)}%</span>
        <span className="spacer" />
        {pdf && <a className="tool" href={pdf.href} download={pdf.name}><Download size={14} aria-hidden="true" />{t('dl_n_pdf')}</a>}
        {dxf && <a className="tool" href={dxf.href} download={dxf.name}><Download size={14} aria-hidden="true" />{t('dl_n_dxf')}</a>}
      </div>
      <div
        className="drawing-stage" tabIndex={0} onKeyDown={onKey} aria-label={t('drawingHint')}
        onWheel={(e) => { setZ((v) => clamp(v * (e.deltaY < 0 ? 1.1 : 1 / 1.1))); }}
        onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, px: p.x, py: p.y }; }}
        onPointerMove={(e) => { const d = drag.current; if (d) setP({ x: d.px + e.clientX - d.x, y: d.py + e.clientY - d.y }); }}
        onPointerUp={() => { drag.current = null; }}
        onPointerCancel={() => { drag.current = null; }}
      >
        <img src={src} alt="three-view drawing" draggable={false} onError={() => setErr(true)}
          style={{ transform: `translate(${p.x}px, ${p.y}px) scale(${z})` }} />
      </div>
      <div className="viewer-foot"><span className="muted hint-text">{t('drawingHint')}</span></div>
    </div>
  );
}
