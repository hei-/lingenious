import { lazy, Suspense, type ComponentProps } from 'react';
import { useI18n } from '../i18n';

const Inner = lazy(() => import('./Viewer').then((m) => ({ default: m.Viewer })));

/** three.js is large: load the viewer chunk on demand. */
export function Viewer(props: ComponentProps<typeof Inner>) {
  const { t } = useI18n();
  return (
    <Suspense fallback={<div className="viewer"><div className="viewer-stage"><div className="viewer-msg"><span className="spinner" />{t('v_loading')}</div></div></div>}>
      <Inner {...props} />
    </Suspense>
  );
}
