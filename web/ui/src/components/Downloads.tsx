import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Box, ChevronDown, ChevronRight, Download, FileArchive, FileCode, FileJson, FileText, Loader2, PencilRuler, ScrollText, type LucideIcon } from 'lucide-react';
import { useI18n, type Key } from '../i18n';
import { downloadName, fileState, formatSize, groupFiles, type FileCtx } from '../lib/files';

const META: Record<string, { icon: LucideIcon; badge: string; k: string }> = {
  'part.step': { icon: Box, badge: 'STEP', k: 'step' },
  'drawing.pdf': { icon: FileText, badge: 'PDF', k: 'pdf' },
  'drawing.dxf': { icon: PencilRuler, badge: 'DXF', k: 'dxf' },
  'part.py': { icon: FileCode, badge: 'PY', k: 'py' },
  'run.json': { icon: FileJson, badge: 'JSON', k: 'json' },
  'log.txt': { icon: ScrollText, badge: 'TXT', k: 'log' },
};

export function FileIcon({ file }: { file: string }) {
  const m = META[file];
  const I = m?.icon ?? FileText;
  return (
    <span className="ficon" aria-hidden="true"><I size={18} strokeWidth={1.6} /><span className="fbadge">{m?.badge ?? ''}</span></span>
  );
}

interface Props {
  title: string; version: number; ctx: FileCtx; sizes?: Record<string, number>; notPassed: boolean; synthetic?: string;
  href: (file: string) => string; zip: string | null; onPick?: () => void;
}

/** Grouped file list (used inside the header download menu). */
export function DownloadList({ title, version, ctx, sizes, notPassed, synthetic, href, zip, onPick }: Props) {
  const { t } = useI18n();
  const [more, setMore] = useState(false);
  const groups = groupFiles(ctx, sizes);
  const anyReady = groups.some((g) => g.items.some((i) => i.state === 'ready'));
  return (
    <div className="dlp">
      <div className="dlp-head">
        <h2 id="dlp-h" className="sec-h">{t('dl_title')} · <span className="num">v{version}</span></h2>
        {synthetic && <span className="badge syn-badge" title={t('syntheticTip')}>✎ {t('synthetic')}</span>}
      </div>
      {notPassed && <p className="dlp-warn" role="note"><AlertTriangle size={14} aria-hidden="true" /> {t('dl_notPassed')}</p>}
      {groups.map((g) => {
        const collapsed = g.collapsed && !more;
        return (
          <div key={g.id} className="dlg">
            {g.collapsed ? (
              <button type="button" className="dlg-toggle" aria-expanded={more} onClick={() => setMore(!more)}>
                {more ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                {t('dl_more')} <span className="muted">· {t('dl_g_records')}</span>
              </button>
            ) : <h3 className="dlg-h">{t(`dl_g_${g.id}` as Key)}</h3>}
            {!collapsed && (
              <ul className="dl-list">
                {g.items.map((it) => {
                  const m = META[it.file];
                  const name = downloadName(title, version, it.file);
                  const body = (
                    <>
                      <FileIcon file={it.file} />
                      <span className="dl-main">
                        <span className="dl-name">{t(`dl_n_${m.k}` as Key)}</span>
                        <span className="dl-fname">{name}</span>
                        <span className="dl-desc">{t(`dl_d_${m.k}` as Key)}</span>
                      </span>
                      <span className="dl-side num">
                        {it.state === 'ready' && <>{formatSize(it.size)}<Download size={16} aria-hidden="true" /></>}
                        {it.state === 'pending' && <><Loader2 size={16} className="spin" aria-hidden="true" />{t('dl_pending')}</>}
                        {it.state === 'failed' && <span className="err-t dl-fail"><AlertTriangle size={16} aria-hidden="true" />{t('dl_failed')}</span>}
                        {it.state === 'missing' && <span className="muted">{t('dl_missing')}</span>}
                      </span>
                    </>
                  );
                  return (
                    <li key={it.file}>
                      {it.state === 'ready'
                        ? <a className="dl-item" href={href(it.file)} download={name} onClick={onPick}>{body}</a>
                        : <div className={'dl-item disabled ' + it.state} aria-disabled="true" title={it.message}>{body}</div>}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
      {zip && anyReady && !ctx.running
        ? <a className="btn block dl-zip" href={zip} download={downloadName(title, version, 'bundle.zip')} onClick={onPick}><FileArchive size={16} aria-hidden="true" />{t('dl_zip')}</a>
        : <span className="btn block dl-zip disabled" aria-disabled="true" title={zip ? undefined : t('dl_zip_off')}><FileArchive size={16} aria-hidden="true" />{t('dl_zip')}</span>}
    </div>
  );
}

/** Header split button: main part downloads STEP, the caret opens the full grouped list. */
export function DownloadMenu(props: Props) {
  const { t } = useI18n();
  const { title, version, ctx, href } = props;
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const caret = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const step = fileState('part.step', ctx);
  const close = (refocus = true) => { setOpen(false); if (refocus) caret.current?.focus(); };

  useEffect(() => {
    if (!open) return;
    const focusables = () => [...(pop.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])') ?? [])];
    requestAnimationFrame(() => focusables()[0]?.focus());
    const onDown = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) close(false); };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const f = focusables(); if (!f.length) return;
        const i = f.indexOf(document.activeElement as HTMLElement);
        f[(i + (e.key === 'ArrowDown' ? 1 : f.length - 1)) % f.length].focus();
        e.preventDefault();
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  return (
    <div className="split" ref={wrap} onBlur={(e) => { if (open && e.relatedTarget && !wrap.current?.contains(e.relatedTarget as Node)) close(false); }}>
      {step.state === 'ready'
        ? <a className="btn primary split-main" href={href('part.step')} download={downloadName(title, version, 'part.step')}><Download size={16} aria-hidden="true" />{t('dl_step_primary')}</a>
        : <span className="btn primary split-main disabled" aria-disabled="true" title={step.state === 'failed' ? step.message : undefined}>
          {step.state === 'pending' ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Download size={16} aria-hidden="true" />}{t('dl_step_primary')}</span>}
      <button ref={caret} type="button" className="btn primary split-caret" aria-haspopup="dialog" aria-expanded={open} aria-label={t('dl_menu')} title={t('dl_menu')} onClick={() => (open ? close() : setOpen(true))}>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {open && (
        <>
          <button type="button" className="split-scrim" aria-label={t('close')} tabIndex={-1} onClick={() => close()} />
          <div ref={pop} className="split-pop" role="dialog" aria-modal="false" aria-labelledby="dlp-h">
            <DownloadList {...props} onPick={() => close()} />
          </div>
        </>
      )}
    </div>
  );
}
