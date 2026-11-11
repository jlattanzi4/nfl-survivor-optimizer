/**
 * Survivor path optimizer. Port of pipeline/optimizer.py; keep the two in sync.
 *
 * Path objective: Σ_weeks [ log p − λ · log fs ], where fs is the expected
 * fraction of the field that survives the week given the pick wins.
 * λ = 0 → maximize win-out probability; λ = 1 → maximize weekly pool EV.
 */
import { assign, BIG } from './hungarian.js';

/** A game is over or under way: it has a result, or its kickoff has passed. */
export function hasStarted(g, now = Date.now()) {
  return g.result != null || (g.kickoff != null && Date.parse(g.kickoff) <= now);
}

/**
 * The games that can still be picked, by week: priced, and not kicked off.
 *
 * `keep` names one team-week to leave in even though it has started: the pick
 * already riding on that game. Once it's final its probability is no longer a
 * forecast, so it becomes 1 for a win and 0 for a loss or tie.
 */
export function indexByWeek(games, { now = Date.now(), keep = null } = {}) {
  const by = new Map();
  for (const g of games) {
    if (g.p == null) continue;                // a week already played, known only from the schedule
    let game = g;
    if (hasStarted(g, now)) {
      if (!keep || g.week !== keep.week || g.team !== keep.team) continue;
      if (g.result != null) game = { ...g, p: g.result === 'W' ? 1 : 0 };
    }
    if (!by.has(game.week)) by.set(game.week, []);
    by.get(game.week).push(game);
  }
  return by;
}

export function fieldSurvival(weekGames, pick) {
  let total = 0;
  for (const g of weekGames) total += g.pick || 0;
  if (total <= 0) return 1;
  let fs = 0;
  for (const g of weekGames) {
    const share = (g.pick || 0) / total;
    fs += g.team === pick ? share : share * g.p;
  }
  return Math.max(fs, 1e-6);
}

function clampP(p) { return Math.min(Math.max(p, 1e-4), 1 - 1e-4); }

export function buildCost(byWeek, weeks, teams, lam) {
  const col = new Map(teams.map((t, j) => [t, j]));
  const cost = weeks.map(() => new Float64Array(teams.length).fill(BIG));
  weeks.forEach((w, i) => {
    const wg = byWeek.get(w) || [];
    for (const g of wg) {
      const j = col.get(g.team);
      if (j === undefined) continue;
      let c = -Math.log(clampP(g.p));
      if (lam > 0) c += lam * Math.log(fieldSurvival(wg, g.team));
      cost[i][j] = c;
    }
  });
  return cost;
}

/**
 * @returns {Array<{week:number, team:string}>|null}
 */
export function bestPath(byWeek, allTeams, used, weeks, lam = 0, force = null) {
  const usedSet = new Set(used);
  const teams = allTeams.filter((t) => !usedSet.has(t)).sort();
  if (weeks.length > teams.length) return null;
  const cost = buildCost(byWeek, weeks, teams, lam);
  if (force !== null) {
    const j = teams.indexOf(force);
    if (j < 0 || cost[0][j] >= BIG) return null;
    cost[0].fill(BIG);
    cost[0][j] = -1e3;
  }
  const a = assign(cost);
  const path = [];
  for (let i = 0; i < weeks.length; i++) {
    if (cost[i][a[i]] >= BIG) return null;
    path.push({ week: weeks[i], team: teams[a[i]] });
  }
  return path;
}

export function pathWinOut(byWeek, path) {
  let p = 1;
  for (const { week, team } of path) {
    const g = (byWeek.get(week) || []).find((x) => x.team === team);
    p *= g ? g.p : 0;
  }
  return p;
}
