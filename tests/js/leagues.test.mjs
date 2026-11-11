import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  applyOffer, content, covers, decodeShare, dropAutoDuplicates, encodeShare, isUntouchedStarter,
  makeLeague, merge3, parseRow, planSync, reconcile, runSync,
} from '../../docs/js/leagues.js';

const league = (over = {}) => makeLeague({ id: 'L1', name: 'Office pool', pool: 120, used: { 1: 'BUF', 2: 'KC' }, ...over });
const row = (l, rev = 'r1') => parseRow({ id: l.id, data: { ...content(l), rev } });

/** An in-memory stand-in for the account's table, with the same write rules. */
function fakeStore(rows = new Map()) {
  return {
    rows,
    async list() { return [...rows].map(([id, data]) => ({ id, data: structuredClone(data) })); },
    async insert(id, data) { if (rows.has(id)) return false; rows.set(id, structuredClone(data)); return true; },
    async update(id, data, expect) {
      const current = rows.get(id);
      if (!current || (current.rev ?? null) !== expect) return false;
      rows.set(id, structuredClone(data));
      return true;
    },
  };
}
const device = (leagues = [makeLeague()]) => ({ leagues, bases: {}, deleted: [], offers: [] });
async function sync(d, store) {
  const out = await runSync(store, { local: d.leagues, bases: d.bases, deleted: d.deleted });
  d.leagues = out.leagues; d.bases = out.bases; d.deleted = out.deleted; d.offers.push(...out.offers);
  return out;
}
const live = (store) => [...store.rows].filter(([, data]) => !data.deleted).map(([id]) => id);

/* ------------------------------------------------------------------ shape */

test('makeLeague fills defaults and drops malformed picks', () => {
  const l = makeLeague({ pool: '0', lives: '2', myStrikes: '5', used: { 3: 'BUF', 19: 'KC', x: 'SF', 4: '' } });
  assert.equal(l.name, 'My pool');
  assert.equal(l.pool, 50);
  assert.equal(l.lives, 2);
  assert.equal(l.myStrikes, 1);
  assert.deepEqual(l.used, { 3: 'BUF' });
  assert.match(l.id, /^L/);
  assert.equal(makeLeague({ myStrikes: 'auto' }).myStrikes, 'auto');
});

test('an untouched starter league is recognised, an edited one is not', () => {
  assert.ok(isUntouchedStarter(makeLeague()));
  assert.ok(!isUntouchedStarter(makeLeague({ used: { 1: 'BUF' } })));
  assert.ok(!isUntouchedStarter(makeLeague({ name: 'Office pool' })));
});

/* ----------------------------------------------------------- shared links */

test('a share link round-trips a league, id and name included', () => {
  const l = league({ lives: 2, fieldStrikes: 14, myStrikes: 1 });
  assert.deepEqual(decodeShare(encodeShare(l)), l);
});

test('links from before share ids existed are still read', () => {
  const l = decodeShare('#w=10&pool=200&used=1:BUF,2:KC,3:ZZZ', (t) => t !== 'ZZZ');
  assert.equal(l.pool, 200);
  assert.deepEqual(l.used, { 1: 'BUF', 2: 'KC' });
  assert.equal(l.name, 'Shared setup');
});

test('a hash with no setup in it decodes to nothing', () => {
  assert.equal(decodeShare(''), null);
  assert.equal(decodeShare('#w=10'), null);
  assert.equal(decodeShare('#access_token=abc&type=magiclink'), null);
});

/* ----------------------------------------------------------------- on load */

test('one saved league plus a foreign link: still one league, same one active, calendar week', () => {
  const saved = { week: 3, leagueId: 'L1', leagues: [league()] };
  const incoming = decodeShare('#w=4&pool=120&used=1:BUF,2:KC,9:DET');
  const out = reconcile({ saved, incoming, calendarWeek: 10 });
  assert.equal(out.leagues.length, 1);
  assert.deepEqual(out.leagues[0], league());
  assert.equal(out.leagueId, 'L1');
  assert.equal(out.week, 10);
  assert.deepEqual(out.offer.used, { 1: 'BUF', 2: 'KC', 9: 'DET' });
});

test('the week last open in this browser does not override the calendar', () => {
  assert.equal(reconcile({ saved: { week: 3, leagueId: 'L1', leagues: [league()] }, calendarWeek: 10 }).week, 10);
});

test('a link that an existing league already covers selects it and offers nothing', () => {
  const other = league({ id: 'L2', name: 'Family', pool: 12, used: { 1: 'DET' } });
  const saved = { leagueId: 'L2', leagues: [other, league()] };
  const stale = decodeShare('#pool=120&used=1:BUF');   // an old address of the office pool
  const out = reconcile({ saved, incoming: stale, calendarWeek: 10 });
  assert.equal(out.offer, null);
  assert.equal(out.leagueId, 'L1');
  assert.equal(out.leagues.length, 2);
});

test('on a first visit the link is where the person starts', () => {
  const out = reconcile({ saved: null, incoming: decodeShare(encodeShare(league())), calendarWeek: 10 });
  assert.deepEqual(out.leagues, [league()]);
  assert.equal(out.offer, null);
});

test('with nothing saved and no link there is exactly one starter league, selected', () => {
  const out = reconcile({ saved: null, calendarWeek: 1 });
  assert.equal(out.leagues.length, 1);
  assert.ok(isUntouchedStarter(out.leagues[0]));
  assert.equal(out.leagueId, out.leagues[0].id);
});

test('a saved selection that no longer exists falls back to the first league', () => {
  assert.equal(reconcile({ saved: { leagueId: 'gone', leagues: [league()] }, calendarWeek: 1 }).leagueId, 'L1');
});

test('an offer changes nothing until answered, and each answer does one thing', () => {
  const state = { leagues: [league()], leagueId: 'L1' };
  const offer = makeLeague({ id: 'L9', name: 'From a friend', pool: 40, used: { 1: 'SF' } });

  assert.deepEqual(applyOffer(state, offer, 'ignore'), state);

  const imported = applyOffer(state, offer, 'import');
  assert.deepEqual(imported.leagues.map((l) => l.id), ['L1', 'L9']);
  assert.equal(imported.leagueId, 'L9');

  const replaced = applyOffer(state, offer, 'replace');
  assert.equal(replaced.leagues.length, 1);
  assert.deepEqual(replaced.leagues[0], makeLeague({ ...offer, id: 'L1', name: 'Office pool' }));

  // Importing a link to a league this browser already has gets its own id.
  const clash = applyOffer(state, makeLeague({ ...offer, id: 'L1' }), 'import');
  assert.equal(new Set(clash.leagues.map((l) => l.id)).size, 2);
});

test('leftover "Shared setup N" leagues are removed only when another league covers them', () => {
  const dup = league({ id: 'L2', name: 'Shared setup 2', used: { 1: 'BUF' } });
  const distinct = league({ id: 'L3', name: 'Shared setup 3', used: { 1: 'BUF', 5: 'GB' } });
  const out = dropAutoDuplicates({ leagues: [league(), dup, distinct], leagueId: 'L2' });
  assert.deepEqual(out.leagues.map((l) => l.id), ['L1', 'L3']);
  assert.deepEqual(out.removed, ['L2']);
  assert.equal(out.leagueId, 'L1');

  const only = league({ name: 'Shared setup 1' });
  assert.equal(dropAutoDuplicates({ leagues: [only], leagueId: 'L1' }).leagues.length, 1);
});

/* ------------------------------------------------------------------- merge */

test('picks recorded for different weeks on two devices both survive', () => {
  const base = league();
  const phone = league({ used: { 1: 'BUF', 2: 'KC', 3: 'DET' } });
  const laptop = league({ used: { 1: 'BUF', 2: 'KC', 4: 'SF' } });
  assert.deepEqual(merge3(base, phone, laptop).used, { 1: 'BUF', 2: 'KC', 3: 'DET', 4: 'SF' });
});

test('the same week changed on both sides takes the account copy', () => {
  const merged = merge3(league(), league({ used: { 1: 'BUF', 2: 'DET' } }), league({ used: { 1: 'BUF', 2: 'SF' } }));
  assert.deepEqual(merged.used, { 1: 'BUF', 2: 'SF' });
});

test('a setting changed on one side only is kept from that side', () => {
  const merged = merge3(league(), league({ pool: 80 }), league({ name: 'Office pool 2026' }));
  assert.equal(merged.pool, 80);
  assert.equal(merged.name, 'Office pool 2026');
});

test('a pick cleared on either side stays cleared', () => {
  assert.deepEqual(merge3(league(), league(), league({ used: { 1: 'BUF' } })).used, { 1: 'BUF' });
  assert.deepEqual(merge3(league(), league({ used: { 1: 'BUF' } }), league()).used, { 1: 'BUF' });
});

test('with no shared history the picks are pooled and the account wins disagreements', () => {
  const merged = merge3(null, league({ pool: 80, used: { 1: 'BUF', 3: 'DET' } }), league({ used: { 1: 'KC', 2: 'SF' } }));
  assert.equal(merged.pool, 120);
  assert.deepEqual(merged.used, { 1: 'KC', 2: 'SF', 3: 'DET' });
});

test('a team spent in different weeks on two devices ends up used once, in the account week', () => {
  const merged = merge3(league(), league({ used: { 1: 'BUF', 2: 'KC', 3: 'DET' } }), league({ used: { 1: 'BUF', 2: 'KC', 5: 'DET' } }));
  assert.deepEqual(merged.used, { 1: 'BUF', 2: 'KC', 5: 'DET' });
});

/* ---------------------------------------------------------------- planning */

test('first sync against an account with leagues uploads nothing extra', () => {
  const remote = [row(league())];
  const untouched = makeLeague();
  const edited = makeLeague({ id: 'Lphone', used: { 3: 'DET' } });
  const covered = makeLeague({ id: 'Lold', pool: 120, used: { 1: 'BUF' } });
  const plan = planSync({ local: [untouched, edited, covered], bases: {}, remote });
  assert.deepEqual(plan.leagues.map((l) => l.id), ['L1']);
  assert.deepEqual(plan.writes, []);
  assert.deepEqual(plan.offers.map((l) => l.id), ['Lphone']);
});

test('a tombstoned league adds nothing and removes the local copy', () => {
  const gone = { id: 'L2', rev: 'r9', deleted: true, content: content(makeLeague()) };
  const plan = planSync({ local: [league(), league({ id: 'L2' })], bases: { L1: { rev: 'r1', content: content(league()) } }, remote: [row(league()), gone] });
  assert.deepEqual(plan.leagues.map((l) => l.id), ['L1']);
  assert.deepEqual(plan.writes, []);
});

test('a league deleted here is tombstoned in the account, not pulled back', () => {
  const second = league({ id: 'L2', name: 'Family' });
  const bases = { L1: { rev: 'r1', content: content(league()) }, L2: { rev: 'r1', content: content(second) } };
  const plan = planSync({ local: [league()], bases, remote: [row(league()), row(second)], deleted: ['L2'] });
  assert.deepEqual(plan.leagues.map((l) => l.id), ['L1']);
  assert.deepEqual(plan.writes, [{ type: 'delete', id: 'L2', expect: 'r1' }]);
});

test('a league whose row has vanished from the account is removed here too', () => {
  const second = league({ id: 'L2' });
  const bases = { L1: { rev: 'r1', content: content(league()) }, L2: { rev: 'r1', content: content(second) } };
  const plan = planSync({ local: [league(), second], bases, remote: [row(league())] });
  assert.deepEqual(plan.leagues.map((l) => l.id), ['L1']);
});

test('a league made after the first sync is uploaded', () => {
  const fresh = league({ id: 'Lnew', name: 'New pool', used: {} });
  const plan = planSync({ local: [league(), fresh], bases: { L1: { rev: 'r1', content: content(league()) } }, remote: [row(league())] });
  assert.deepEqual(plan.writes, [{ type: 'insert', id: 'Lnew', content: content(fresh) }]);
  assert.equal(plan.leagues.length, 2);
});

test('rows written before revisions existed parse with a null revision', () => {
  const parsed = parseRow({ id: 'L1', data: { id: 'L1', name: 'Office pool', pool: 120, lives: 1, fieldStrikes: 0, myStrikes: 'auto', used: { 1: 'BUF' } } });
  assert.equal(parsed.rev, null);
  assert.equal(parsed.deleted, false);
  assert.deepEqual(parsed.content.used, { 1: 'BUF' });
});

/* ------------------------------------------------------------ whole syncs */

test('two devices, one league: edits on both arrive on both and no league appears', async () => {
  const store = fakeStore();
  const laptop = device([league()]);
  await sync(laptop, store);                       // first device uploads its league

  const phone = device();                          // a new browser with only the starter league
  await sync(phone, store);
  assert.deepEqual(phone.leagues, [league()]);     // it adopts the account's league
  assert.deepEqual(phone.offers, []);

  phone.leagues[0].used[3] = 'DET';
  laptop.leagues[0].used[4] = 'SF';
  await sync(phone, store);
  await sync(laptop, store);
  await sync(phone, store);

  const expected = { 1: 'BUF', 2: 'KC', 3: 'DET', 4: 'SF' };
  assert.deepEqual(laptop.leagues[0].used, expected);
  assert.deepEqual(phone.leagues[0].used, expected);
  assert.deepEqual(live(store), ['L1']);
  assert.equal(laptop.leagues.length, 1);
  assert.equal(phone.leagues.length, 1);
});

test('a browser with its own picks signing in gets an offer, and the account is left alone', async () => {
  const store = fakeStore();
  await sync(device([league()]), store);
  const phone = device([makeLeague({ id: 'Lphone', used: { 3: 'DET' } })]);
  await sync(phone, store);
  assert.deepEqual(phone.leagues, [league()]);
  assert.deepEqual(phone.offers.map((l) => l.id), ['Lphone']);
  assert.deepEqual(live(store), ['L1']);
});

test('a delete on one device reaches the other and is not undone by it', async () => {
  const store = fakeStore();
  const laptop = device([league(), league({ id: 'L2', name: 'Family' })]);
  await sync(laptop, store);
  const phone = device();
  await sync(phone, store);
  assert.equal(phone.leagues.length, 2);

  laptop.leagues = laptop.leagues.filter((l) => l.id !== 'L2');
  laptop.deleted = ['L2'];
  await sync(laptop, store);
  assert.deepEqual(laptop.deleted, []);

  phone.leagues.find((l) => l.id === 'L2').used[5] = 'GB';   // the phone still has it, and edits it
  await sync(phone, store);
  assert.deepEqual(phone.leagues.map((l) => l.id), ['L1']);
  await sync(laptop, store);
  assert.deepEqual(laptop.leagues.map((l) => l.id), ['L1']);
  assert.deepEqual(live(store), ['L1']);
});

test('a write that lands between read and write is merged, not overwritten', async () => {
  const store = fakeStore();
  const laptop = device([league()]);
  await sync(laptop, store);
  const phone = device();
  await sync(phone, store);

  // The phone's update is beaten once by the laptop writing week 4 first.
  laptop.leagues[0].used[4] = 'SF';
  phone.leagues[0].used[3] = 'DET';
  const realUpdate = store.update;
  let raced = false;
  store.update = async (...args) => {
    if (!raced) { raced = true; store.update = realUpdate; await sync(laptop, store); }
    return realUpdate(...args);
  };
  const out = await sync(phone, store);
  assert.ok(raced);
  assert.ok(out.settled);
  assert.deepEqual(phone.leagues[0].used, { 1: 'BUF', 2: 'KC', 3: 'DET', 4: 'SF' });
  assert.deepEqual(content(makeLeague(store.rows.get('L1'))).used, { 1: 'BUF', 2: 'KC', 3: 'DET', 4: 'SF' });
});

test('an account written by the old version syncs without duplicating anything', async () => {
  const legacy = { id: 'L1', name: 'Office pool', pool: 120, lives: 1, fieldStrikes: 0, myStrikes: 'auto', used: { 1: 'BUF', 2: 'KC' } };
  const store = fakeStore(new Map([['L1', legacy]]));
  const laptop = device([league({ used: { 1: 'BUF', 2: 'KC', 3: 'DET' } })]);   // same id, one newer pick
  await sync(laptop, store);
  assert.deepEqual(live(store), ['L1']);
  assert.deepEqual(laptop.leagues[0].used, { 1: 'BUF', 2: 'KC', 3: 'DET' });
  assert.ok(store.rows.get('L1').rev);
});

test('covers: same rules and no pick the other lacks', () => {
  assert.ok(covers(league(), league({ used: { 1: 'BUF' } })));
  assert.ok(!covers(league({ used: { 1: 'BUF' } }), league()));
  assert.ok(!covers(league(), league({ pool: 121, used: {} })));
});
