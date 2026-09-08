/**
 * Survivor UI. Loads data/season.json, runs the engine in a Web Worker,
 * and renders the gauntlet, the call, the candidate list, the path table
 * and the full grid.
 */
import { analyze } from './engine.js';

const N_SIMS = 20000;
const LAM_LABEL = { 0: 'Safest path', 0.5: 'Balanced', 1: 'Leverage', 1.5: 'Max leverage' };
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, children = []) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else if (k === 'html') n.innerHTML = v;
    else if (k === 'text') n.textContent = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null) n.append(c);
  return n;
};

/* ------------------------------------------------------------- formatting */
const MINUS = '−';
const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const ml = (x) => (x == null ? '' : x > 0 ? `+${x}` : `${MINUS}${Math.abs(x)}`);
const spread = (s) => (s === 0 ? 'PK' : s < 0 ? `${MINUS}${Math.abs(s)}` : `+${s}`);
const siteWord = (site) => (site === 'away' ? 'at' : 'vs');
const matchup = (g) => `${siteWord(g.site)} ${g.opp}${g.site === 'neutral' ? ' (n)' : ''}`;
const shortMatchup = (g) => `${siteWord(g.site)} ${g.opp}`;
const times = (x) => `${x.toFixed(x >= 10 ? 0 : 1)}×`;
const relTime = (iso) => {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
};

/* -------------------------------------------------------------------- state */
const state = {
  data: null,
  teams: new Map(),
  week: 1,
  calendarWeek: 1,
  leagues: [],         // [{ id, name, pool, lives, fieldStrikes, myStrikes: 'auto'|0|1, used: { week: abbr } }]
  leagueId: null,
  selected: null,      // abbr of the selected candidate
  result: null,
  view: 'call',
};
const newLeague = (over = {}) => ({ id: `L${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, name: 'My pool', pool: 50, lives: 1, fieldStrikes: 0, myStrikes: 'auto', used: {}, ...over });
const league = () => state.leagues.find((l) => l.id === state.leagueId) || state.leagues[0];

function loadPersisted() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('survivor:v3') || 'null'); } catch { /* ignore */ }
  if (!saved) {
    // migrate the single-league v2 shape
    try {
      const v2 = JSON.parse(localStorage.getItem('survivor:v2') || 'null');
      if (v2) saved = { week: v2.week, leagues: [newLeague({ pool: v2.pool || 50, used: v2.used || {} })] };
    } catch { /* ignore */ }
  }
  saved = saved || {};
  if (Array.isArray(saved.leagues) && saved.leagues.length) {
    state.leagues = saved.leagues.map((l) => newLeague(l));
    state.leagueId = saved.leagueId;
  }
  if (!state.leagues.length) state.leagues = [newLeague()];
  if (!league()) state.leagueId = state.leagues[0].id;
  state.leagueId = league().id;
  if (Number.isFinite(saved.week) && saved.week >= 1 && saved.week <= 18) state.week = saved.week;

  // URL hash overrides the active league (shareable links)
  const h = new URLSearchParams(location.hash.slice(1));
  const L = league();
  if (h.get('w')) { const w = Number(h.get('w')); if (w >= 1 && w <= 18) state.week = w; }
  if (h.get('pool')) { const v = Number(h.get('pool')); if (v >= 2) L.pool = Math.round(v); }
  if (h.get('lives')) L.lives = Number(h.get('lives')) === 2 ? 2 : 1;
  if (h.has('fs')) L.fieldStrikes = Math.max(0, Number(h.get('fs')) || 0);
  if (h.has('ms')) L.myStrikes = h.get('ms') === 'auto' ? 'auto' : Math.min(1, Math.max(0, Number(h.get('ms')) || 0));
  if (h.has('used')) {
    L.used = {};
    for (const pair of h.get('used').split(',').filter(Boolean)) {
      const [w, t] = pair.split(':');
      if (state.teams.has(t)) L.used[Number(w)] = t;
    }
  }
  for (const l of state.leagues) for (const [w, t] of Object.entries(l.used)) if (!state.teams.has(t)) delete l.used[w];
}

function persist() {
  try { localStorage.setItem('survivor:v3', JSON.stringify({ week: state.week, leagueId: state.leagueId, leagues: state.leagues })); } catch { /* ignore */ }
  const L = league();
  const used = Object.entries(L.used).filter(([w]) => Number(w) < state.week);
  const h = new URLSearchParams();
  h.set('w', state.week);
  h.set('pool', L.pool);
  if (L.lives > 1) { h.set('lives', L.lives); h.set('fs', L.fieldStrikes); h.set('ms', L.myStrikes); }
  if (used.length) h.set('used', used.map(([w, t]) => `${w}:${t}`).join(','));
  history.replaceState(null, '', `#${h.toString()}`);
}

const usedList = () => Object.entries(league().used).filter(([w]) => Number(w) < state.week).map(([, t]) => t);

/** Strikes I have taken so far: counted from recorded results unless overridden. */
function recordedLosses() {
  let n = 0;
  for (const [w, t] of Object.entries(league().used)) {
    if (Number(w) >= state.week) continue;
    const g = gameOf(Number(w), t);
    if (g?.result === 'L' || g?.result === 'T') n++;
  }
  return n;
}
function myStrikes() {
  const L = league();
  if (L.lives <= 1) return 0;
  return L.myStrikes === 'auto' ? recordedLosses() : Number(L.myStrikes);
}

/* --------------------------------------------------------------- data lookup */
const gameIndex = new Map();
function indexGames() {
  for (const g of state.data.games) gameIndex.set(`${g.week}:${g.team}`, g);
}
const gameOf = (week, team) => gameIndex.get(`${week}:${team}`);

function calendarWeek() {
  const now = Date.now();
  let w = 1;
  state.data.week_starts.forEach((iso, i) => { if (now >= new Date(iso).getTime()) w = i + 1; });
  return w;
}

/* --------------------------------------------------------------------- logo */
function logo(abbr, size = 44) {
  const t = state.teams.get(abbr);
  const span = el('span', { class: 'logo', style: `--s:${size}px;--c1:${t.colors[0]};--c2:${t.colors[1]}` });
  const img = el('img', { src: `https://a.espncdn.com/i/teamlogos/nfl/500-dark/${t.espn}.png`, alt: '', loading: 'lazy', width: size, height: size });
  img.addEventListener('error', () => img.classList.add('is-broken'));
  span.append(img, document.createTextNode(abbr));
  return span;
}

/* ------------------------------------------------------------------ worker */
let worker = null;
let jobId = 0;
const pending = new Map();
const SYNC = new URLSearchParams(location.search).has('sync');   // ?sync=1 runs the engine on the main thread
function getWorker() {
  if (worker) return worker;
  if (SYNC) return null;
  try {
    worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
    worker.onmessage = (e) => {
      const { id, result, error } = e.data;
      const p = pending.get(id);
      if (!p) return;
      pending.delete(id);
      error ? p.reject(new Error(error)) : p.resolve(result);
    };
    worker.onerror = () => { worker = null; };
  } catch { worker = null; }
  return worker;
}
function runAnalysis(options) {
  const w = getWorker();
  if (!w) return Promise.resolve(analyze(state.data, options));
  const id = ++jobId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    w.postMessage({ id, data: state.data, options });
  });
}

let runTimer = null;
function scheduleRun() {
  clearTimeout(runTimer);
  runTimer = setTimeout(run, 120);
}
async function run() {
  persist();
  renderControls();
  renderGauntlet();
  showLoading(`Running the season ${N_SIMS.toLocaleString()} times…`);
  const L = league();
  const options = { used: usedList(), currentWeek: state.week, poolSize: L.pool, nSims: N_SIMS, seed: 7, lives: L.lives, myStrikes: myStrikes(), fieldStrikes: L.fieldStrikes };
  const myJob = ++jobId + 0.5;
  state.lastJob = myJob;
  try {
    const result = await runAnalysis(options);
    if (state.lastJob !== myJob) return;
    state.result = result;
    if (!result.candidates.some((c) => c.team === state.selected)) state.selected = result.candidates[0]?.team ?? null;
    renderAll();
  } catch (err) {
    showLoading(`Something went wrong: ${err.message}`, true);
    console.error(err);
  }
}

/** Overlay the call card with a loading message; the card keeps its last content underneath. */
function showLoading(message, failed = false) {
  const card = $('#call');
  let box = $('#callEmpty');
  if (!box) {
    box = el('div', { class: 'call-empty', id: 'callEmpty' }, [el('div', { class: 'spinner', 'aria-hidden': 'true' }), el('p')]);
    card.prepend(box);
  }
  box.hidden = false;
  box.classList.toggle('is-overlay', card.children.length > 1);
  box.querySelector('.spinner').hidden = failed;
  box.querySelector('p').textContent = message;
}

/* ------------------------------------------------------------------ render */
const selectedCandidate = () => state.result?.candidates.find((c) => c.team === state.selected) || null;

function renderAll() {
  renderCandidates();
  renderCall();
  renderGauntlet(true);
  renderPath();
  renderGrid();
}

function renderStatus() {
  const s = state.data.sources;
  const parts = [];
  parts.push(`Lines as of <b>${relTime(state.data.generated_at)}</b>`);
  parts.push(`SurvivorGrid wk ${state.data.grid_week}`);
  if (s.odds_api && !s.odds_api.error) parts.push(`market lines on ${Math.round((s.odds_api.applied || 0) / 2)} games`);
  else parts.push('market lines off');
  $('#status').innerHTML = parts.join(' · ');
  $('#footData').textContent = `Data ${new Date(state.data.generated_at).toLocaleString()} · ${state.data.games.length} team-weeks`;
  $('#seasonLabel').textContent = state.data.season;
}

function renderControls() {
  const L = league();
  const sel = $('#leagueSelect');
  sel.replaceChildren();
  for (const l of state.leagues) sel.append(el('option', { value: l.id, text: l.name }));
  sel.append(el('option', { value: '__new', text: '+ New league…' }));
  sel.value = L.id;
  $('#poolSize').value = L.pool;
  for (const b of $('#poolChips').children) b.classList.toggle('is-active', Number(b.dataset.pool) === L.pool);
  const ms = myStrikes();
  $('#livesLine').textContent = L.lives > 1 ? `Two lives · ${ms} strike${ms === 1 ? '' : 's'}` : 'Single elimination';
  renderLives();
  const wsel = $('#weekSelect');
  if (!wsel.children.length) {
    for (let w = 1; w <= 18; w++) wsel.append(el('option', { value: w, text: `Week ${w}${w === state.calendarWeek ? ' (now)' : ''}` }));
  }
  wsel.value = state.week;
  const n = usedList().length;
  $('#usedCount').textContent = `${n} team${n === 1 ? '' : 's'}`;
  $('#simNote').textContent = `${N_SIMS.toLocaleString()} seasons`;
}

function renderLives() {
  const L = league();
  const box = $('#lives');
  box.replaceChildren();
  if (L.lives <= 1) { box.append(el('span', { text: L.name })); return; }
  const used = Math.min(myStrikes(), L.lives);
  const pips = el('span', { class: 'pips', 'aria-hidden': 'true' });
  for (let i = 0; i < L.lives; i++) pips.append(el('i', { class: `pip${i < used ? ' spent' : ''}` }));
  box.append(el('span', { text: L.name }), pips, el('span', { text: used >= L.lives ? 'eliminated' : `${L.lives - used} of ${L.lives} lives left` }));
}

function renderGauntlet(cascade = false) {
  const list = $('#slots');
  list.replaceChildren();
  const cand = selectedCandidate();
  const pathBy = new Map((cand?.path || []).map((p) => [p.week, p]));
  for (let w = 1; w <= 18; w++) {
    const li = el('li', { class: 'slot' });
    const isPast = w < state.week;
    const isNow = w === state.week;
    li.classList.add(isPast ? 'slot--past' : isNow ? 'slot--now' : 'slot--future');
    const btn = el('button', { class: 'slot-btn', type: 'button' });
    btn.append(el('span', { class: 'slot-num', html: `<small>WEEK</small>${w}` }));
    const ring = el('span', { class: 'slot-ring' });
    let team = null;
    let sub = '';
    let subClass = 'slot-sub';
    if (isPast) {
      team = league().used[w] || null;
      if (team) {
        const g = gameOf(w, team);
        if (g?.result) {
          li.append(el('span', { class: `slot-result ${g.result}`, text: g.result === 'W' ? '✓' : g.result === 'L' ? '✗' : '–' }));
          if (g.result === 'L') li.classList.add('is-lost');
        }
        sub = g ? shortMatchup(g) : '';
      } else { sub = 'Add'; subClass += ' add'; }
      btn.setAttribute('aria-label', `Week ${w}: ${team ? `used ${state.teams.get(team).name}` : 'no pick recorded'}. Change`);
      btn.addEventListener('click', () => openPicker(w));
    } else if (isNow) {
      team = cand?.team || null;
      sub = team ? `${pct(cand.thisWeek.p, 0)} ${shortMatchup(cand.thisWeek)}` : 'This week';
      btn.setAttribute('aria-label', `Week ${w}: this week's call${team ? `, ${state.teams.get(team).name}` : ''}`);
      btn.addEventListener('click', () => $('#candList').scrollIntoView({ behavior: 'smooth', block: 'center' }));
    } else {
      const p = pathBy.get(w);
      team = p?.team || null;
      sub = p ? `${pct(p.p, 0)} ${shortMatchup(p)}` : '';
      btn.tabIndex = -1;
      btn.setAttribute('aria-label', `Week ${w}${team ? `: ${state.teams.get(team).name}` : ''}`);
    }
    if (team) { ring.append(logo(team, 52)); li.classList.add('is-filled'); }
    btn.append(ring, el('span', { class: 'slot-team', text: team || '' }), el('span', { class: subClass, text: sub }));
    li.append(btn);
    if (cascade && !isPast) { li.classList.add('is-cascade'); li.style.setProperty('--i', w - state.week); }
    list.append(li);
  }
}

function renderCandidates() {
  const list = $('#candList');
  list.replaceChildren();
  const r = state.result;
  if (!r.candidates.length) {
    list.append(el('li', { class: 'cand-empty', text: 'No playable path from here. Check the week and your used teams.' }));
    return;
  }
  list.append(el('li', { class: 'cand-head', html: '<span></span><span></span><span>Team</span><span class="hide-sm">Win</span><span>Public</span><span>Pool equity</span>' }));
  const maxEq = Math.max(...r.candidates.map((c) => c.equity));
  r.candidates.forEach((c, i) => {
    const btn = el('button', { class: `cand${c.team === state.selected ? ' is-selected' : ''}`, type: 'button', 'aria-pressed': String(c.team === state.selected) });
    btn.append(
      el('span', { class: 'cand-rank', text: i + 1 }),
      logo(c.team, 34),
      el('span', { class: 'cand-name' }, [el('b', { text: state.teams.get(c.team).nick }), el('span', { text: `${matchup(c.thisWeek)} ${spread(c.thisWeek.spread)}${c.lam > 0 ? ` · ${LAM_LABEL[c.lam]}` : ''}` })]),
      el('span', { class: 'cand-num hide-sm', html: `${pct(c.thisWeek.p)}<small>this wk</small>` }),
      el('span', { class: 'cand-num', html: `${pct(c.thisWeek.pick)}<small>on it</small>` }),
      el('span', { class: 'cand-eq' }, [el('b', { text: times(c.equity * league().pool) }), el('span', { class: 'bar' }, el('i', { style: `--w:${(c.equity / maxEq) * 100}%` }))]),
    );
    btn.addEventListener('click', () => { state.selected = c.team; renderAll(); });
    list.append(el('li', {}, btn));
  });
}

function renderCall() {
  const card = $('#call');
  const c = selectedCandidate();
  card.replaceChildren();
  if (!c) {
    card.append(el('div', { class: 'call-empty' }, el('p', { text: 'Nothing to call yet.' })));
    return;
  }
  const t = state.teams.get(c.team);
  const g = c.thisWeek;
  const weeksLeft = c.path.length;
  const rank = state.result.candidates.findIndex((x) => x.team === c.team) + 1;
  const L = league();
  const ms = myStrikes();
  const twoLives = L.lives > 1;
  if (twoLives && ms >= L.lives) card.append(el('p', { class: 'eliminated', text: `You have ${ms} strikes recorded, which is elimination in a two-lives pool. Showing the numbers as if you were on your last life.` }));
  card.append(
    el('div', { class: 'eyebrow' }, [el('span', { text: `The call · Week ${state.week} · ${twoLives ? `two lives, ${Math.min(ms, 1)} strike${ms === 1 ? '' : 's'}` : 'single elimination'} · #${rank} of ${state.result.candidates.length}` }), el('span', { class: `tag${c.lam === 0 ? '' : ' tag--flag'}`, text: LAM_LABEL[c.lam] })]),
    el('div', { class: 'call-team' }, [
      logo(c.team, 92),
      el('div', { class: 'call-name', html: `${t.nick}<small>${t.city} · ${matchup(g)} · ${spread(g.spread)}${g.ml != null ? ` · ${ml(g.ml)}` : ''}${g.src === 'market' ? ' <span class="src src--market">market</span>' : ''}</small>` }),
    ]),
    el('div', { class: 'stats' }, [
      stat('Win this week', pct(g.p), g.src === 'market' ? 'de-vigged consensus' : 'from the line'),
      stat('Public on it', pct(g.pick), g.pick > 0.2 ? 'heavy chalk' : g.pick > 0.08 ? 'popular' : 'contrarian'),
      twoLives
        ? stat('Survive season', pct(c.pSurvive, 1), ms === 0 ? `${pct(c.pClean, 1)} without a strike` : `on your last life · ${pct(c.winOut, 2)} to win out`)
        : stat('Win out', pct(c.winOut, 2), `${weeksLeft} straight`),
      stat('Pool equity', times(c.equity * L.pool), `${pct(c.equity, 1)} of the pot · ${pct(c.pWinOutright, 1)} outright`, true),
    ]),
    el('div', { class: 'charts' }, [
      chartCard('Chance you are still alive', survivalChart(state.result.weeks, c.curve)),
      chartCard(`Entries still alive (${L.pool.toLocaleString()} now${twoLives ? ', two lives' : ''})`, survivorsChart(state.result.weeks, state.result.survivors, L.pool)),
    ]),
  );
}
function stat(label, value, sub, flag = false) {
  return el('div', { class: 'stat' }, [el('div', { class: 'stat-label', text: label }), el('div', { class: `stat-value${flag ? ' flag' : ''}`, text: value }), el('div', { class: 'stat-sub', text: sub })]);
}
function chartCard(title, svg) { return el('div', { class: 'chart' }, [el('h4', { text: title }), svg]); }

/* ------------------------------------------------------------------ charts */
const SVG_NS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs = {}) => { const n = document.createElementNS(SVG_NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };

function lineChart({ weeks, values, yMax, fmt, flag, fill }) {
  const W = 440, H = 170, L = 34, R = 10, T = 12, B = 24;
  const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' });
  const x = (i) => L + (i / Math.max(1, weeks.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - v / yMax) * (H - T - B);
  for (const f of [0, 0.5, 1]) {
    svg.append(svgEl('line', { class: 'grid-line', x1: L, x2: W - R, y1: y(f * yMax), y2: y(f * yMax) }));
    const tick = svgEl('text', { class: 'tick', x: L - 6, y: y(f * yMax) + 3, 'text-anchor': 'end' });
    tick.textContent = fmt(f * yMax);
    svg.append(tick);
  }
  weeks.forEach((w, i) => {
    if (weeks.length > 10 && i % 2) return;
    const tk = svgEl('text', { class: 'tick', x: x(i), y: H - 6, 'text-anchor': 'middle' });
    tk.textContent = w;
    svg.append(tk);
  });
  const pts = values.map((v, i) => [x(i), y(v)]);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
  if (fill) svg.append(svgEl('path', { class: `area${flag ? ' area--flag' : ''}`, d: `${d}L${x(pts.length - 1)},${y(0)}L${x(0)},${y(0)}Z` }));
  svg.append(svgEl('path', { class: `series${flag ? ' series--flag' : ''}`, d }));
  const last = pts[pts.length - 1];
  svg.append(svgEl('circle', { class: `dot${flag ? ' dot--flag' : ''}`, cx: last[0], cy: last[1], r: 4 }));
  const lbl = svgEl('text', { class: 'label', x: last[0] - 6, y: last[1] - 8, 'text-anchor': 'end' });
  lbl.textContent = fmt(values[values.length - 1]);
  svg.append(lbl);

  // hover layer
  const cross = svgEl('line', { class: 'crosshair', y1: T, y2: H - B, x1: 0, x2: 0, visibility: 'hidden' });
  const hdot = svgEl('circle', { class: `dot${flag ? ' dot--flag' : ''}`, r: 4, visibility: 'hidden' });
  const hit = svgEl('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' });
  svg.append(cross, hdot, hit);
  const tip = $('#tooltip');
  hit.addEventListener('mousemove', (e) => {
    const box = svg.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    let i = 0;
    for (let k = 1; k < pts.length; k++) if (Math.abs(pts[k][0] - px) < Math.abs(pts[i][0] - px)) i = k;
    cross.setAttribute('x1', pts[i][0]); cross.setAttribute('x2', pts[i][0]); cross.setAttribute('visibility', 'visible');
    hdot.setAttribute('cx', pts[i][0]); hdot.setAttribute('cy', pts[i][1]); hdot.setAttribute('visibility', 'visible');
    showTip(e, `<b>Week ${weeks[i]}</b><br>${fmt(values[i])}`);
  });
  hit.addEventListener('mouseleave', () => { cross.setAttribute('visibility', 'hidden'); hdot.setAttribute('visibility', 'hidden'); hideTip(); });
  return svg;
}
const survivalChart = (weeks, curve) => lineChart({ weeks, values: curve, yMax: 1, fmt: (v) => pct(v, 0), flag: true, fill: true });
const survivorsChart = (weeks, survivors, pool) => lineChart({ weeks, values: survivors, yMax: pool, fmt: (v) => Math.round(v).toLocaleString(), flag: false, fill: true });

/* ------------------------------------------------------------------- path */
function renderPath() {
  const c = selectedCandidate();
  const sec = $('#pathSection');
  sec.hidden = !c;
  if (!c) return;
  const tbody = $('#pathTable tbody');
  tbody.replaceChildren();
  let cum = 1;
  for (const p of c.path) {
    cum *= p.p;
    const t = state.teams.get(p.team);
    const tr = el('tr', { class: p.week === state.week ? 'is-now' : '' });
    tr.append(
      el('td', { class: 'wk', text: p.week }),
      el('td', {}, el('span', { class: 'pick-cell' }, [logo(p.team, 28), el('b', { text: t.name })])),
      el('td', { html: `${matchup(p)}${p.src === 'market' ? '<span class="src src--market">market</span>' : ''}` }),
      el('td', { class: 'num', text: `${spread(p.spread)}${p.ml != null ? `  ${ml(p.ml)}` : ''}` }),
      el('td', { class: 'num', text: pct(p.p) }),
      el('td', { class: 'num', html: `${pct(p.pick)}<span class="src">${p.pickSrc === 'public' ? 'public' : 'proj.'}</span>` }),
      el('td', { class: 'num', text: pct(cum, 1) }),
    );
    tbody.append(tr);
  }
  $('#pathSummary').textContent = `${c.path.length} weeks · ${pct(c.winOut, 2)} to run the table${league().lives > 1 ? ` · ${pct(c.pSurvive, 1)} to survive with two lives` : ''} · pool equity ${times(c.equity * league().pool)} an average entry`;
}

/* ------------------------------------------------------------------- grid */
function heat(p) {
  // diverging: ember (underdog) → neutral at 50% → grass (favorite)
  const stops = [[0.25, [90, 42, 38]], [0.5, [27, 42, 33]], [0.7, [36, 90, 54]], [0.92, [62, 154, 86]]];
  const v = Math.min(0.92, Math.max(0.25, p));
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) if (v >= stops[i][0] && v <= stops[i + 1][0]) { a = stops[i]; b = stops[i + 1]; }
  const f = (v - a[0]) / (b[0] - a[0] || 1);
  const c = a[1].map((x, i) => Math.round(x + (b[1][i] - x) * f));
  return `rgb(${c.join(',')})`;
}
function renderGrid() {
  const table = $('#gridTable');
  table.replaceChildren();
  const c = selectedCandidate();
  const pathBy = new Map((c?.path || []).map((p) => [`${p.week}:${p.team}`, true]));
  const used = new Set(usedList());
  const weeks = [];
  for (let w = 1; w <= 18; w++) weeks.push(w);
  const thead = el('thead');
  const hr = el('tr');
  hr.append(el('th', { class: 'team', text: 'Team' }));
  for (const w of weeks) hr.append(el('th', { class: w === state.week ? 'now' : '', text: w, scope: 'col' }));
  thead.append(hr);
  table.append(thead);
  const tbody = el('tbody');
  const rows = [...state.teams.values()].sort((a, b) => {
    const pa = gameOf(state.week, a.abbr)?.p ?? 0, pb = gameOf(state.week, b.abbr)?.p ?? 0;
    return pb - pa;
  });
  for (const t of rows) {
    const tr = el('tr', { class: used.has(t.abbr) ? 'used' : '' });
    tr.append(el('th', { class: 'team', scope: 'row' }, el('span', { class: 'pick-cell' }, [logo(t.abbr, 24), el('b', { text: t.abbr })])));
    for (const w of weeks) {
      const g = gameOf(w, t.abbr);
      if (!g) { tr.append(el('td', { class: 'bye', text: 'BYE' })); continue; }
      const td = el('td');
      if (g.result || w < state.week) {
        td.classList.add('done');
        if (g.result) td.classList.add(g.result);
        td.append(el('span', { text: g.result || '·' }), el('span', { class: 'opp', text: matchup(g) }));
      } else {
        td.style.background = heat(g.p);
        td.append(el('span', { text: pct(g.p, 0) }), el('span', { class: 'opp', text: `${g.site === 'away' ? '@' : ''}${g.opp}` }));
        if (pathBy.has(`${w}:${t.abbr}`)) td.classList.add('path');
      }
      td.addEventListener('mousemove', (e) => showTip(e, `<b>Week ${w} · ${t.abbr} ${matchup(g)}</b><br>${spread(g.spread)}${g.ml != null ? ` · ${ml(g.ml)}` : ''} · win ${pct(g.p)}<br><span class="muted">${g.pick != null ? `public ${pct(g.pick)} (${g.pick_src === 'public' ? 'actual' : 'projected'})` : ''}${g.result ? `result ${g.result}` : ''}</span>`));
      td.addEventListener('mouseleave', hideTip);
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
}

/* --------------------------------------------------------------- tooltip */
function showTip(e, html) {
  const tip = $('#tooltip');
  tip.innerHTML = html;
  tip.hidden = false;
  const pad = 14;
  let x = e.clientX + pad, y = e.clientY + pad;
  const r = tip.getBoundingClientRect();
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
function hideTip() { $('#tooltip').hidden = true; }

/* ---------------------------------------------------------------- picker */
let pickerWeek = null;
function openPicker(week) {
  pickerWeek = week;
  $('#pickerTitle').textContent = `Week ${week}`;
  const grid = $('#pickerGrid');
  grid.replaceChildren();
  const L = league();
  const takenBy = new Map(Object.entries(L.used).filter(([w]) => Number(w) !== week && Number(w) < state.week).map(([w, t]) => [t, Number(w)]));
  for (const t of state.teams.values()) {
    const b = el('button', { type: 'button', class: `pick-opt${L.used[week] === t.abbr ? ' is-current' : ''}${takenBy.has(t.abbr) ? ' is-taken' : ''}` });
    b.append(logo(t.abbr, 36), document.createTextNode(t.abbr));
    if (takenBy.has(t.abbr)) b.append(el('small', { text: `wk ${takenBy.get(t.abbr)}` }));
    b.addEventListener('click', () => {
      for (const [w, tt] of Object.entries(L.used)) if (tt === t.abbr) delete L.used[w];
      L.used[week] = t.abbr;
      closePicker();
      scheduleRun();
    });
    grid.append(b);
  }
  $('#picker').hidden = false;
  grid.querySelector('button')?.focus();
}
function closePicker() { $('#picker').hidden = true; }

/* ---------------------------------------------------------- league dialog */
let dialogLeagueId = null;   // null = creating
function openLeagueDialog(id) {
  dialogLeagueId = id;
  const L = id ? state.leagues.find((l) => l.id === id) : newLeague({ name: '' });
  $('#leagueTitle').textContent = id ? 'Edit league' : 'New league';
  $('#leagueName').value = L.name;
  $('#leaguePool').value = L.pool;
  for (const r of document.querySelectorAll('input[name="lives"]')) r.checked = Number(r.value) === L.lives;
  $('#leagueFieldStrikes').value = L.fieldStrikes;
  $('#leagueMyStrikes').value = String(L.myStrikes);
  $('#leagueDelete').hidden = !id || state.leagues.length < 2;
  syncStrikeFields();
  $('#leagueDialog').hidden = false;
  $('#leagueName').focus();
}
function syncStrikeFields() {
  const lives = Number(document.querySelector('input[name="lives"]:checked')?.value || 1);
  $('#strikeFields').hidden = lives < 2;
}
function closeLeagueDialog() { $('#leagueDialog').hidden = true; renderControls(); }
function saveLeagueDialog(e) {
  e.preventDefault();
  const name = $('#leagueName').value.trim() || 'My pool';
  const pool = Math.max(2, Math.round(Number($('#leaguePool').value) || 2));
  const lives = Number(document.querySelector('input[name="lives"]:checked')?.value || 1) === 2 ? 2 : 1;
  const fieldStrikes = Math.max(0, Math.round(Number($('#leagueFieldStrikes').value) || 0));
  const msRaw = $('#leagueMyStrikes').value;
  const myStrikesV = msRaw === 'auto' ? 'auto' : Number(msRaw);
  if (dialogLeagueId) {
    Object.assign(state.leagues.find((l) => l.id === dialogLeagueId), { name, pool, lives, fieldStrikes, myStrikes: myStrikesV });
  } else {
    const L = newLeague({ name, pool, lives, fieldStrikes, myStrikes: myStrikesV });
    state.leagues.push(L);
    state.leagueId = L.id;
  }
  $('#leagueDialog').hidden = true;
  scheduleRun();
}
function deleteLeague() {
  if (!dialogLeagueId || state.leagues.length < 2) return;
  const L = state.leagues.find((l) => l.id === dialogLeagueId);
  if (!confirm(`Delete "${L.name}" and its recorded picks?`)) return;
  state.leagues = state.leagues.filter((l) => l.id !== dialogLeagueId);
  state.leagueId = state.leagues[0].id;
  $('#leagueDialog').hidden = true;
  scheduleRun();
}

/* ------------------------------------------------------------------ tabs */
function setView(name) {
  state.view = name;
  for (const b of document.querySelectorAll('.tab')) { const on = b.dataset.tab === name; b.classList.toggle('is-active', on); b.setAttribute('aria-pressed', String(on)); }
  for (const v of document.querySelectorAll('.view')) { const on = v.id === `view-${name}`; v.classList.toggle('is-active', on); v.hidden = !on; }
}

/* ------------------------------------------------------------------- init */
async function init() {
  const resp = await fetch(`data/season.json?v=${Math.floor(Date.now() / 3.6e6)}`);
  if (!resp.ok) { $('#status').textContent = 'Could not load season data.'; return; }
  state.data = await resp.json();
  for (const t of state.data.teams) state.teams.set(t.abbr, t);
  indexGames();
  state.calendarWeek = calendarWeek();
  state.week = state.calendarWeek;
  loadPersisted();
  renderStatus();

  $('#poolSize').addEventListener('change', (e) => { const v = Math.round(Number(e.target.value)); if (v >= 2) { league().pool = v; scheduleRun(); } });
  $('#poolChips').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { league().pool = Number(b.dataset.pool); scheduleRun(); } });
  $('#leagueSelect').addEventListener('change', (e) => {
    if (e.target.value === '__new') { openLeagueDialog(null); e.target.value = state.leagueId; return; }
    state.leagueId = e.target.value; state.selected = null; scheduleRun();
  });
  $('#editLeague').addEventListener('click', () => openLeagueDialog(state.leagueId));
  $('#leagueForm').addEventListener('submit', saveLeagueDialog);
  $('#leagueClose').addEventListener('click', closeLeagueDialog);
  $('#leagueCancel').addEventListener('click', closeLeagueDialog);
  $('#leagueDelete').addEventListener('click', deleteLeague);
  for (const r of document.querySelectorAll('input[name="lives"]')) r.addEventListener('change', syncStrikeFields);
  $('#leagueDialog').addEventListener('click', (e) => { if (e.target === e.currentTarget) closeLeagueDialog(); });
  $('#weekSelect').addEventListener('change', (e) => { state.week = Number(e.target.value); scheduleRun(); });
  $('#clearUsed').addEventListener('click', () => { league().used = {}; scheduleRun(); });
  $('#pickerClose').addEventListener('click', closePicker);
  $('#pickerClear').addEventListener('click', () => { delete league().used[pickerWeek]; closePicker(); scheduleRun(); });
  $('#picker').addEventListener('click', (e) => { if (e.target === e.currentTarget) closePicker(); });
  document.addEventListener('keydown', (e) => { if (e.key !== 'Escape') return; if (!$('#picker').hidden) closePicker(); if (!$('#leagueDialog').hidden) closeLeagueDialog(); });
  for (const b of document.querySelectorAll('.tab')) b.addEventListener('click', () => setView(b.dataset.tab));

  run();
}

init();
