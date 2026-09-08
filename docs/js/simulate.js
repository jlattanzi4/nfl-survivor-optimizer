/**
 * Monte Carlo pool simulator. Port of pipeline/simulate.py; keep in sync.
 *
 * The field's trajectory is independent of my pick, so it is drawn once and
 * every candidate path is scored against the same outcomes.
 */

/** mulberry32: small, fast, seedable. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand) {
  let u = 0;
  while (u === 0) u = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand());
}

export function binomial(n, p, rand) {
  if (n <= 0 || p <= 0) return 0;
  if (p >= 1) return n;
  if (n <= 64) {
    let k = 0;
    for (let i = 0; i < n; i++) if (rand() < p) k++;
    return k;
  }
  const mean = n * p;
  const sd = Math.sqrt(n * p * (1 - p));
  const k = Math.round(mean + sd * gaussian(rand));
  return Math.min(n, Math.max(0, k));
}

export function prepare(byWeek, weeks) {
  return weeks.map((w) => {
    const wg = byWeek.get(w) || [];
    const key = (g) => [g.team, g.opp].sort().join('|');
    const gameIdx = new Map();
    const p0 = [];
    for (const g of wg) {
      const k = key(g);
      if (!gameIdx.has(k)) {
        gameIdx.set(k, p0.length);
        const first = k.split('|')[0];
        p0.push(g.team === first ? g.p : 1 - g.p);
      }
    }
    let tot = 0;
    for (const g of wg) tot += g.pick || 0;
    const teams = wg.map((g) => ({
      team: g.team,
      gi: gameIdx.get(key(g)),
      side: g.team === key(g).split('|')[0] ? 0 : 1,
      share: tot > 0 ? (g.pick || 0) / tot : 0,
    }));
    return { week: w, p0: Float64Array.from(p0), teams, byTeam: new Map(teams.map((t) => [t.team, t])) };
  });
}

/**
 * @param {object} opts  lives: strikes allowed before elimination (1 = single elimination);
 *                       fieldStrikes: entries in the field already sitting on their last life.
 */
export function simulateField(prep, poolSize, nSims, rand, { lives = 1, fieldStrikes = 0 } = {}) {
  const W = prep.length;
  const won = [];
  const alive = new Array(W + 1);
  const field = Math.max(0, poolSize - 1);
  // bucket[k][s] = entries with k strikes in sim s
  let bucket = [];
  for (let k = 0; k < lives; k++) bucket.push(new Int32Array(nSims));
  const onLast = lives > 1 ? Math.min(fieldStrikes, field) : 0;
  bucket[0].fill(field - onLast);
  if (lives > 1) bucket[lives - 1].fill(onLast);
  alive[0] = new Int32Array(nSims).fill(field);
  const frac = new Float64Array(nSims);
  for (let i = 0; i < W; i++) {
    const pw = prep[i];
    const G = pw.p0.length;
    const out = new Uint8Array(nSims * G);
    for (let s = 0; s < nSims; s++) {
      for (let g = 0; g < G; g++) out[s * G + g] = rand() < pw.p0[g] ? 1 : 0;
    }
    won.push(out);
    frac.fill(0);
    for (const t of pw.teams) {
      if (!t.share) continue;
      for (let s = 0; s < nSims; s++) {
        const w = out[s * G + t.gi] ^ t.side;
        if (w) frac[s] += t.share;
      }
    }
    const next = bucket.map(() => new Int32Array(nSims));
    const total = new Int32Array(nSims);
    for (let s = 0; s < nSims; s++) {
      const f = Math.min(1, frac[s]);
      for (let k = 0; k < lives; k++) {
        const n = bucket[k][s];
        if (!n) continue;
        const surv = binomial(n, f, rand);
        next[k][s] += surv;
        if (k + 1 < lives) next[k + 1][s] += n - surv;   // losers spend a life
      }
      for (let k = 0; k < lives; k++) total[s] += next[k][s];
    }
    bucket = next;
    alive[i + 1] = total;
  }
  return { won, alive, nSims, lives };
}

export function scorePath(prep, field, path, { lives = 1, myStrikes = 0 } = {}) {
  const { won, alive, nSims } = field;
  const W = prep.length;
  const weekIdx = new Map(prep.map((pw, i) => [pw.week, i]));
  const meAlive = new Uint8Array(nSims).fill(1);
  const strikes = new Uint8Array(nSims).fill(Math.min(myStrikes, lives - 1));
  const settled = new Uint8Array(nSims);
  const payout = new Float64Array(nSims);
  const curve = [];
  for (const { week, team } of path) {
    const i = weekIdx.get(week);
    const pw = prep[i];
    const t = pw.byTeam.get(team);
    const G = pw.p0.length;
    const before = alive[i];
    const after = alive[i + 1];
    let aliveCount = 0;
    for (let s = 0; s < nSims; s++) {
      const myWin = won[i][s * G + t.gi] ^ t.side;
      if (meAlive[s] && !myWin) {
        strikes[s]++;
        if (strikes[s] >= lives) {
          meAlive[s] = 0;
          if (!settled[s]) {
            if (after[s] === 0) payout[s] = 1 / (before[s] + 1);
            settled[s] = 1;
          }
        }
      }
      if (!settled[s] && meAlive[s] && after[s] === 0) { payout[s] = 1; settled[s] = 1; }
      aliveCount += meAlive[s];
    }
    curve.push(aliveCount / nSims);
  }
  let outright = 0;
  let sum = 0;
  let clean = 0;
  for (let s = 0; s < nSims; s++) {
    if (!settled[s] && meAlive[s]) payout[s] = 1 / (alive[W][s] + 1);
    sum += payout[s];
    if (payout[s] === 1) outright++;
    if (meAlive[s] && strikes[s] === 0) clean++;
  }
  return {
    equity: sum / nSims,
    pWinOutright: outright / nSims,
    pSurvive: curve.length ? curve[curve.length - 1] : 1,
    pClean: clean / nSims,
    curve,
  };
}

export function expectedSurvivors(field) {
  return field.alive.slice(1).map((a) => {
    let s = 0;
    for (let i = 0; i < a.length; i++) s += a[i];
    return s / a.length + 1;
  });
}
