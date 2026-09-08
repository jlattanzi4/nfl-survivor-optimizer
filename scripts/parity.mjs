// Dump JS optimizer paths for parity testing against the Python reference.
// usage: node scripts/parity.mjs docs/data/season.json '<json options>'
import { readFileSync } from 'node:fs';
import { indexByWeek, bestPath, pathWinOut } from '../docs/js/optimizer.js';

const data = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const opts = JSON.parse(process.argv[3] || '{}');
const byWeek = indexByWeek(data.games);
const teams = data.teams.map((t) => t.abbr);
const weeks = opts.weeks;
const out = [];
for (const force of opts.forces) {
  for (const lam of opts.lambdas) {
    const path = bestPath(byWeek, teams, opts.used || [], weeks, lam, force);
    out.push({ force, lam, path: path ? path.map((p) => [p.week, p.team]) : null,
               winOut: path ? pathWinOut(byWeek, path) : null });
  }
}
process.stdout.write(JSON.stringify(out));
