export type DiffOp = { type: 'eq' | 'add' | 'del'; text: string; a?: number; b?: number };

/** Minimal line diff (common prefix/suffix trim + LCS table). a/b are 1-based line numbers. */
export function diffLines(oldText: string, newText: string): DiffOp[] {
  const A = oldText === '' ? [] : oldText.replace(/\r\n/g, '\n').split('\n');
  const B = newText === '' ? [] : newText.replace(/\r\n/g, '\n').split('\n');
  let s = 0;
  while (s < A.length && s < B.length && A[s] === B[s]) s++;
  let ea = A.length, eb = B.length;
  while (ea > s && eb > s && A[ea - 1] === B[eb - 1]) { ea--; eb--; }
  const a = A.slice(s, ea), b = B.slice(s, eb);
  const n = a.length, m = b.length;
  const w = m + 1;
  const dp = new Uint32Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i * w + j] = a[i] === b[j] ? dp[(i + 1) * w + j + 1] + 1 : Math.max(dp[(i + 1) * w + j], dp[i * w + j + 1]);
  const out: DiffOp[] = [];
  for (let i = 0; i < s; i++) out.push({ type: 'eq', text: A[i], a: i + 1, b: i + 1 });
  let i = 0, j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { out.push({ type: 'eq', text: a[i], a: s + i + 1, b: s + j + 1 }); i++; j++; }
    else if (j < m && (i === n || dp[i * w + j + 1] >= dp[(i + 1) * w + j])) { out.push({ type: 'add', text: b[j], b: s + j + 1 }); j++; }
    else { out.push({ type: 'del', text: a[i], a: s + i + 1 }); i++; }
  }
  for (let k = ea; k < A.length; k++) out.push({ type: 'eq', text: A[k], a: k + 1, b: eb + (k - ea) + 1 });
  return out;
}

export function diffStats(ops: DiffOp[]) {
  let add = 0, del = 0;
  for (const o of ops) { if (o.type === 'add') add++; else if (o.type === 'del') del++; }
  return { add, del };
}

/** Collapse long unchanged runs, keeping `ctx` lines around changes. Returns ops plus {type:'gap'} markers. */
export type DiffRow = DiffOp | { type: 'gap'; count: number };
export function collapseContext(ops: DiffOp[], ctx = 3): DiffRow[] {
  const keep = new Array(ops.length).fill(false);
  ops.forEach((o, i) => {
    if (o.type !== 'eq') for (let k = Math.max(0, i - ctx); k <= Math.min(ops.length - 1, i + ctx); k++) keep[k] = true;
  });
  if (!keep.some(Boolean)) return ops.length ? [{ type: 'gap', count: ops.length }] : [];
  const rows: DiffRow[] = [];
  let skipped = 0;
  ops.forEach((o, i) => {
    if (keep[i]) { if (skipped) { rows.push({ type: 'gap', count: skipped }); skipped = 0; } rows.push(o); }
    else skipped++;
  });
  if (skipped) rows.push({ type: 'gap', count: skipped });
  return rows;
}
