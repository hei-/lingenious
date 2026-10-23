import type { PartSpec } from '../types';
import type { Dims } from './scene';

export function bboxDims(spec?: PartSpec): Dims {
  const b = spec?.assertions?.bbox;
  return b && b.x > 0 ? { x: b.x, y: b.y, z: b.z } : { x: 100, y: 60, z: 40 };
}

export function fmtDate(s: string | undefined, lang: string): string {
  if (!s) return '';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
