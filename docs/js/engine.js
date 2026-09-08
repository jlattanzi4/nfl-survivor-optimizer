/**
 * Candidate generation + ranking. Runs inside the Web Worker.
 */
import { indexByWeek, bestPath, pathWinOut } from './optimizer.js';
import { prepare, simulateField, scorePath, expectedSurvivors, rng } from './simulate.js';

export const LAMBDAS = [0, 0.5, 1];
export const LAMBDAS_TWO_LIVES = [0, 0.5, 1, 1.5];

export function analyze(data, { used, currentWeek, poolSize, nSims = 20000, seed = 7, lambdas, lives = 1, myStrikes = 0, fieldStrikes = 0 }) {
  lambdas = lambdas || (lives > 1 ? LAMBDAS_TWO_LIVES : LAMBDAS);
  myStrikes = Math.min(Math.max(0, myStrikes), lives - 1);
  const byWeek = indexByWeek(data.games);
  const weeks = [];
  for (let w = currentWeek; w <= 18; w++) if ((byWeek.get(w) || []).length) weeks.push(w);
  const allTeams = data.teams.map((t) => t.abbr);
  const thisWeek = byWeek.get(currentWeek) || [];
  const usedSet = new Set(used);
  const playing = thisWeek.map((g) => g.team).filter((t) => !usedSet.has(t)).sort();

  const seen = new Map();
  for (const team of playing) {
    for (const lam of lambdas) {
      const path = bestPath(byWeek, allTeams, used, weeks, lam, team);
      if (!path) continue;
      const key = path.map((p) => p.team).join(',');
      if (!seen.has(key)) seen.set(key, { team, lam, path });
      else seen.get(key).lams = [...(seen.get(key).lams || [seen.get(key).lam]), lam];
    }
  }

  const prep = prepare(byWeek, weeks);
  const field = simulateField(prep, poolSize, nSims, rng(seed), { lives, fieldStrikes });
  const survivors = expectedSurvivors(field);

  const candidates = [...seen.values()].map((c) => {
    const s = scorePath(prep, field, c.path, { lives, myStrikes });
    const g = thisWeek.find((x) => x.team === c.team);
    return {
      team: c.team,
      lam: c.lam,
      path: c.path.map(({ week, team }) => {
        const gg = (byWeek.get(week) || []).find((x) => x.team === team);
        return { week, team, opp: gg.opp, site: gg.site, spread: gg.spread, p: gg.p, pick: gg.pick, ml: gg.ml, src: gg.src, pickSrc: gg.pick_src };
      }),
      thisWeek: { p: g.p, pick: g.pick, opp: g.opp, site: g.site, spread: g.spread, ml: g.ml, src: g.src },
      winOut: pathWinOut(byWeek, c.path),
      equity: s.equity,
      pWinOutright: s.pWinOutright,
      pSurvive: s.pSurvive,
      pClean: s.pClean,
      curve: s.curve,
    };
  });
  candidates.sort((a, b) => b.equity - a.equity);

  // Best-by-team: one row per this-week team, its best-equity path.
  const byTeam = new Map();
  for (const c of candidates) if (!byTeam.has(c.team)) byTeam.set(c.team, c);

  return {
    weeks,
    poolSize,
    lives,
    myStrikes,
    nSims,
    survivors,
    candidates: [...byTeam.values()],
    allPaths: candidates.length,
  };
}
