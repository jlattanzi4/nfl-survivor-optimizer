import assert from 'node:assert/strict';
import { test } from 'node:test';

import { analyze } from '../../docs/js/engine.js';
import { hasStarted, indexByWeek } from '../../docs/js/optimizer.js';

const NOW = Date.parse('2026-11-15T19:00:00Z');          // Sunday, an hour after the early kickoffs
const EARLY = '2026-11-15T18:00:00Z';
const LATE = '2026-11-15T21:25:00Z';
const TEAMS = ['BUF', 'NYJ', 'KC', 'DEN', 'SF', 'LV', 'DAL', 'NYG'];

/** Both sides of one game. */
function game(week, home, away, p, { kickoff = null, result = null } = {}) {
  const flip = { W: 'L', L: 'W', T: 'T' };
  const side = (team, opp, site, prob, res) => ({ week, team, opp, site, spread: 0, p: prob, pick: 0.25, src: 'spread', kickoff, result: res });
  return [side(home, away, 'home', p, result), side(away, home, 'away', p == null ? null : 1 - p, result && flip[result])];
}
/** Week 10 with two early games under way or final, two late games to come; week 11 untouched. */
const season = (earlyResult = null) => ({
  teams: TEAMS.map((abbr) => ({ abbr })),
  games: [
    ...game(9, 'BUF', 'KC', null, { kickoff: '2026-11-08T18:00:00Z', result: 'W' }),   // already played, no price
    ...game(10, 'BUF', 'NYJ', 0.8, { kickoff: EARLY, result: earlyResult }),
    ...game(10, 'KC', 'DEN', 0.7, { kickoff: EARLY }),
    ...game(10, 'SF', 'LV', 0.75, { kickoff: LATE }),
    ...game(10, 'DAL', 'NYG', 0.6, { kickoff: LATE }),
    ...game(11, 'BUF', 'DEN', 0.7), ...game(11, 'KC', 'LV', 0.8), ...game(11, 'SF', 'NYG', 0.7), ...game(11, 'DAL', 'NYJ', 0.6),
  ],
});
const run = (data, over = {}) => analyze(data, { used: [], currentWeek: 10, poolSize: 20, nSims: 400, now: NOW, ...over });

test('a game has started once it has a result or its kickoff has passed', () => {
  assert.ok(hasStarted({ result: 'W' }, NOW));
  assert.ok(hasStarted({ result: null, kickoff: EARLY }, NOW));
  assert.ok(!hasStarted({ result: null, kickoff: LATE }, NOW));
  assert.ok(!hasStarted({ result: null }, NOW));             // no kickoff known: treated as upcoming
});

test('only games that are priced and not yet kicked off can be picked', () => {
  const byWeek = indexByWeek(season().games, { now: NOW });
  assert.equal(byWeek.has(9), false);
  assert.deepEqual(byWeek.get(10).map((g) => g.team).sort(), ['DAL', 'LV', 'NYG', 'SF']);
  assert.equal(byWeek.get(11).length, 8);
});

test('teams whose games have kicked off are not offered this week', () => {
  const out = run(season());
  assert.deepEqual(out.candidates.map((c) => c.team).sort(), ['DAL', 'LV', 'NYG', 'SF']);
  assert.equal(out.riding, false);
});

test('a lock on a game that has not started changes nothing about what is offered', () => {
  const out = run(season(), { locked: 'SF' });
  assert.equal(out.riding, false);
  assert.equal(out.candidates.length, 4);
});

test('a lock on a game under way is the only candidate, at its pre-game probability', () => {
  const out = run(season(), { locked: 'BUF' });
  assert.equal(out.riding, true);
  assert.deepEqual(out.candidates.map((c) => c.team), ['BUF']);
  assert.equal(out.candidates[0].thisWeek.p, 0.8);
  assert.equal(out.candidates[0].path[0].team, 'BUF');
  assert.ok(!out.candidates[0].path.slice(1).some((p) => p.team === 'BUF'));   // still used once
});

test('once the locked game is final its probability is the result', () => {
  const won = run(season('W'), { locked: 'BUF' });
  assert.equal(won.candidates[0].thisWeek.p, 1);
  const lost = run(season('L'), { locked: 'BUF' });
  assert.equal(lost.candidates[0].thisWeek.p, 0);
  assert.equal(lost.candidates[0].winOut, 0);
  // The data handed in is not rewritten.
  assert.equal(season('L').games.find((g) => g.week === 10 && g.team === 'BUF').p, 0.8);
});

test('when every game this week has kicked off there is nothing to offer', () => {
  const out = run(season(), { now: Date.parse('2026-11-16T03:00:00Z') });
  assert.deepEqual(out.candidates, []);
});
