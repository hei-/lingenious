import { T } from './i18n.js';

const $ = (s, r = document) => r.querySelector(s);
const root = document.documentElement;
let lang = 'en';
if ((navigator.language || '').toLowerCase().startsWith('zh')) lang = 'zh';
try { const s = localStorage.getItem('lg-lang'); if (s) lang = s; } catch (e) {}

const t = (k, vars) => {
  let s = (T[lang] && T[lang][k]) ?? T.en[k] ?? k;
  if (vars) for (const [a, b] of Object.entries(vars)) s = s.replaceAll('{' + a + '}', b);
  return s;
};

// ------------------------------------------------------------ static i18n
function applyStatic() {
  root.lang = lang === 'zh' ? 'zh-CN' : 'en';
  document.title = t('meta.title');
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.innerHTML = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-attr]').forEach((el) => {
    const [attr, key] = el.dataset.i18nAttr.split(':'); el.setAttribute(attr, t(key));
  });
  $('#lang').textContent = t('ui.lang');
}

// ------------------------------------------------------------ results tables
const R = {
  main: {
    head: ['res.col.cfg', 'res.col.first', 'res.col.final', 'res.col.rounds', 'res.col.tokens'],
    rows: [
      ['res.cfgA', [86, 76, 92], [90, 81, 95], '1.08', '3681'],
      ['res.cfgB', [89, 80, 94], [94, 87, 98], '1.31', '4274'],
      ['res.cfgC', [94, 86, 98], [99, 92, 100], '1.27', '4350'],
    ],
  },
  dfm: {
    head: ['res.col.cfg', 'res.col.finaltruth', 'res.col.l3', 'res.col.rounds', 'res.col.tokens', 'res.col.disp'],
    rows: [
      ['res.cfgA', [92, 78, 97], '2.36', '1.00', '3008', '0'],
      ['res.cfgB', [92, 78, 97], '2.36', '1.17', '3326', '3'],
      ['res.cfgC', [89, 75, 96], '1.67', '2.89', '7702', '46'],
    ],
  },
};
const pct = ([v, lo, hi]) =>
  `${v}% [${lo}-${hi}]<span class="iv" aria-hidden="true"><i style="left:${lo}%;width:${hi - lo}%"></i><b style="left:${v}%"></b></span>`;
function renderResults() {
  for (const [id, d] of [['t-main', R.main], ['t-dfm', R.dfm]]) {
    const rows = d.rows.map((r) => '<tr>' + r.map((c, i) => {
      if (i === 0) return `<th scope="row" style="color:var(--fg);font-weight:600">${t(c)}</th>`;
      return `<td class="n">${Array.isArray(c) ? pct(c) : c}</td>`;
    }).join('') + '</tr>').join('');
    $('#' + id).innerHTML = `<thead><tr>${d.head.map((h) => `<th>${t(h)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody>`;
  }
}

// ------------------------------------------------------------ replay
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let replay = null, cur = 0, viewer = null, playTimer = null, glOK = true;
const roundLabel = (n) => (lang === 'zh' ? `第 ${n} 轮` : `Round ${n}`);

function renderTimeline() {
  $('#timeline').innerHTML = replay.rounds.map((r, i) => {
    const ok = !r.issues.some((x) => x.severity === 'error');
    return `<li><button type="button" data-i="${i}" class="${ok ? 'ok' : ''}" ${i === cur ? 'aria-current="true"' : ''}>
      <span class="t1"><span>${roundLabel(r.n)}</span><span class="${ok ? 'st-ok' : 'st-fail'}">${t(ok ? 'replay.passed' : 'replay.failed')}</span></span>
      <span class="t2">${r.seconds} ${t('replay.sec')} · ${r.issues.length ? r.issues.map((x) => x.rule + (x.severity === 'warning' ? ' (!)' : '')).join(', ') : t('replay.noissues')}</span></button></li>`;
  }).join('');
}

function renderGrid() {
  const rs = replay.rounds, rules = replay.checked_rules;
  const g = $('#rule-grid');
  g.style.setProperty('--n', rs.length);
  let h = '<span></span>' + rs.map((r) => `<span class="h">${r.n}</span>`).join('');
  for (const rule of rules) {
    h += `<span>${rule}</span>` + rs.map((r, i) => {
      const hit = r.issues.filter((x) => x.rule === rule);
      const bad = hit.some((x) => x.severity === 'error'), warn = !bad && hit.length > 0;
      return `<span class="c ${bad ? 'badc' : 'okc'}" title="${bad ? t('replay.fail') : warn ? t('replay.sev.warning') : t('replay.ok')}">${bad ? '✕' : warn ? '!' : '·'}</span>`;
    }).join('');
  }
  g.innerHTML = h;
}

function renderIssues(r) {
  const el = $('#issues');
  if (!r.issues.length) { el.innerHTML = `<div class="pass-box">${t('replay.noissues')}</div>`; return; }
  el.innerHTML = r.issues.map((x) => {
    const gloss = lang === 'en' ? (T.en['replay.gloss.' + x.rule] || '') : '';
    const hg = lang === 'en' ? (T.en['replay.hintgloss.' + x.rule] || '') : '';
    return `<div class="issue ${x.severity}">
      <div class="hd"><code>${esc(x.rule)}</code><span class="badge">${esc(x.level)}</span><span class="badge ${x.severity}">${t('replay.sev.' + x.severity)}</span></div>
      <span class="lab">${t('replay.orig')}</span>
      <p class="zhmsg" lang="zh-CN">${esc(x.message)}</p>
      ${gloss ? `<p class="gloss">${gloss}</p>` : ''}
      <p class="nums">${t('replay.measured')} ${x.measured} · ${t('replay.required')} ${x.required}</p>
      <span class="lab">${t('replay.hint')}</span>
      <p class="zhmsg" lang="zh-CN">${esc(x.hint)}</p>
      ${hg ? `<p class="gloss">${hg}</p>` : ''}
    </div>`;
  }).join('');
}

function renderCode(r) {
  // lines in the final script that round 1 lacks are highlighted
  const first = new Set(replay.rounds[0].code.split('\n').map((l) => l.trim()).filter(Boolean));
  const isFinal = r === replay.rounds[replay.rounds.length - 1];
  const lines = r.code.split('\n').map((l) => {
    const add = isFinal && l.trim() && !first.has(l.trim());
    const cls = add ? 'ln add' : 'ln';
    const body = esc(l).replace(/(#.*)$/, '<span class="cm">$1</span>');
    return `<span class="${cls}">${body || ' '}</span>`;
  });
  $('#code').innerHTML = lines.join('');
  $('#code-note').textContent = (r.code_reconstructed ? '' : t('replay.real') + ' ') + (isFinal ? t('replay.added') : '');
}

async function showRound(i, fromUser) {
  cur = i;
  const r = replay.rounds[i];
  if (fromUser) stopPlay();
  renderTimeline(); renderIssues(r); renderCode(r);
  const loc = (r.issues.find((x) => x.location) || {}).location || null;
  if (viewer && glOK) {
    try { await viewer.show('data/' + r.model, loc); }
    catch (e) { console.warn('viewer:', e); fallback(); }
  }
}

function fallback() {
  glOK = false;
  $('#gl').hidden = true;
  const img = $('#gl-fallback'); img.src = 'assets/render.png'; img.hidden = false;
  $('#v-hint').textContent = t('replay.nogl');
  document.querySelector('.v-tools').hidden = true;
}

function stopPlay() { clearInterval(playTimer); playTimer = null; $('#rp-play').textContent = t('replay.play'); }
function togglePlay() {
  if (playTimer) return stopPlay();
  $('#rp-play').textContent = t('replay.pause');
  if (cur >= replay.rounds.length - 1) showRound(0);
  playTimer = setInterval(() => {
    if (cur >= replay.rounds.length - 1) return stopPlay();
    showRound(cur + 1);
  }, 2600);
}

function renderSpec() {
  const s = replay.spec;
  const rows = s.features.map((f) => `<tr><th scope="row">${esc(f.type)}</th><td>${esc(Object.entries(f.dims).map(([k, v]) => `${k} ${v}`).join(', '))}</td></tr>`).join('');
  const a = s.assertions;
  $('#spec').innerHTML = `<table lang="zh-CN"><tbody>${rows}</tbody></table>
    <p class="tiny" style="margin:.6rem 0 .2rem"><code>assertions</code>: bbox ${a.bbox.x}×${a.bbox.y}×${a.bbox.z} (±${a.bbox.tol}), ${a.hole_count} holes, Ø ${a.hole_diameters.join(', ')}</p>
    <p class="tiny muted" style="margin:.6rem 0 .2rem">${t('replay.defaults')}</p>
    <ul lang="zh-CN">${s.defaults_used.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>`;
}

function renderUsage() {
  const u = replay.usage, rs = replay.rounds;
  $('#usage').textContent = t('replay.usage', { calls: u.calls, p: u.prompt_tokens, c: u.completion_tokens, n: rs.length, s: rs.reduce((a, r) => a + r.seconds, 0).toFixed(1) });
}

function renderReplay() {
  if (!replay) return;
  $('#req-text').textContent = replay.requirement;
  renderGrid(); renderSpec(); renderUsage(); showRound(cur);
  $('#rp-play').textContent = playTimer ? t('replay.pause') : t('replay.play');
}

async function initReplay() {
  try {
    replay = await (await fetch('data/replay.json')).json();
  } catch (e) {
    $('#replay-app').innerHTML = `<p class="callout">replay.json could not be loaded (${esc(e.message)}). Serve this folder over HTTP, e.g. <code>python3 -m http.server</code>.</p>`;
    return;
  }
  $('#timeline').addEventListener('click', (e) => { const b = e.target.closest('button[data-i]'); if (b) showRound(+b.dataset.i, true); });
  $('#rp-prev').addEventListener('click', () => showRound(Math.max(0, cur - 1), true));
  $('#rp-next').addEventListener('click', () => showRound(Math.min(replay.rounds.length - 1, cur + 1), true));
  $('#rp-play').addEventListener('click', togglePlay);
  try {
    const { Viewer } = await import('./viewer.js');
    viewer = new Viewer($('#gl'));
    $('#v-edges').addEventListener('change', (e) => viewer.setEdges(e.target.checked));
    $('#v-marker').addEventListener('change', (e) => viewer.setMarker(e.target.checked));
    $('#v-reset').addEventListener('click', () => viewer.reset());
  } catch (e) { console.warn('three.js unavailable:', e); fallback(); }
  renderReplay();
}

// ------------------------------------------------------------ chrome
function setLang(l) {
  lang = l;
  try { localStorage.setItem('lg-lang', l); } catch (e) {}
  applyStatic(); renderResults(); renderReplay();
}
$('#lang').addEventListener('click', () => setLang(lang === 'zh' ? 'en' : 'zh'));
$('#theme').addEventListener('click', () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  const next = dark ? 'light' : 'dark';
  root.dataset.theme = next;
  try { localStorage.setItem('lg-theme', next); } catch (e) {}
  if (viewer) viewer.setTheme();
});
matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => viewer && viewer.setTheme());

applyStatic(); renderResults(); initReplay();
