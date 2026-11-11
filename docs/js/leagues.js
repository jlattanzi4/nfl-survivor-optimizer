/**
 * League state, kept apart from the page so it can be tested: what a league
 * is, what the app shows on load, how a shared link is read, and how this
 * browser's copy is merged with the account's copy.
 *
 * One rule runs through all of it: the app never creates, replaces or removes
 * a league on its own. A setup arriving in a link, or left in a browser that
 * then signs in to an account with leagues of its own, becomes an "offer" for
 * the person to accept or decline.
 */

export const STARTER = { name: 'My pool', pool: 50, lives: 1, fieldStrikes: 0, myStrikes: 'auto', used: {} };
const SETTINGS = ['name', 'pool', 'lives', 'fieldStrikes', 'myStrikes'];

export const newId = () => `L${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
export const newRev = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

/** A league with every field present and well-formed. Unknown fields are dropped. */
export function makeLeague(over = {}) {
  const used = {};
  for (const [w, t] of Object.entries(over.used || {})) {
    const week = Number(w);
    if (Number.isInteger(week) && week >= 1 && week <= 18 && typeof t === 'string' && t) used[week] = t;
  }
  const strikes = over.myStrikes;
  return {
    id: over.id || newId(),
    name: String(over.name || STARTER.name).slice(0, 60),
    pool: Math.max(2, Math.round(Number(over.pool) || STARTER.pool)),
    lives: Number(over.lives) === 2 ? 2 : 1,
    fieldStrikes: Math.max(0, Math.round(Number(over.fieldStrikes) || 0)),
    myStrikes: strikes === undefined || strikes === null || strikes === 'auto' ? 'auto' : Math.min(1, Math.max(0, Number(strikes) || 0)),
    used,
  };
}

/** The part of a league that syncs and is compared: everything but its id. */
export const content = (l) => ({ name: l.name, pool: l.pool, lives: l.lives, fieldStrikes: l.fieldStrikes, myStrikes: l.myStrikes, used: { ...l.used } });
// Week keys are integers, so an object's picks always serialize in week order.
const serialized = (l) => JSON.stringify(content(l));
export const sameContent = (a, b) => serialized(a) === serialized(b);
const sameRules = (a, b) => a.pool === b.pool && a.lives === b.lives && a.fieldStrikes === b.fieldStrikes && String(a.myStrikes) === String(b.myStrikes);
/** True when `a` has `b`'s rules and every pick `b` has, so `b` adds nothing to it. */
export const covers = (a, b) => sameRules(a, b) && Object.entries(b.used).every(([w, t]) => a.used[w] === t);
export const isUntouchedStarter = (l) => l.name === STARTER.name && sameRules(l, STARTER) && Object.keys(l.used).length === 0;

/* ------------------------------------------------------------ shared links */

/** The hash for a link that carries one league. */
export function encodeShare(l) {
  const p = new URLSearchParams();
  p.set('share', l.id);
  p.set('name', l.name);
  p.set('pool', l.pool);
  if (l.lives > 1) { p.set('lives', l.lives); p.set('fs', l.fieldStrikes); p.set('ms', l.myStrikes); }
  const used = Object.entries(l.used);
  if (used.length) p.set('used', used.map(([w, t]) => `${w}:${t}`).join(','));
  return `#${p.toString()}`;
}

/**
 * Read a league out of a link's hash, or null if the hash carries none.
 * Also reads links made before share links had an id or a name, when every
 * page address carried the open league.
 */
export function decodeShare(hash, isTeam = () => true) {
  const h = new URLSearchParams(String(hash || '').replace(/^#/, ''));
  if (!h.has('share') && !h.has('pool') && !h.has('used') && !h.has('lives')) return null;
  const used = {};
  for (const pair of (h.get('used') || '').split(',').filter(Boolean)) {
    const [w, t] = pair.split(':');
    if (isTeam(t)) used[w] = t;
  }
  return makeLeague({
    id: h.get('share') || undefined,
    name: h.get('name') || 'Shared setup',
    pool: h.get('pool'),
    lives: h.get('lives'),
    fieldStrikes: h.get('fs'),
    myStrikes: h.has('ms') ? h.get('ms') : 'auto',
    used,
  });
}

/* ------------------------------------------------------------------ on load */

/**
 * What the app shows when it opens.
 *
 * Saved leagues come back exactly as saved, and the week is always the
 * calendar week, whatever was open last time. A setup arriving in the link
 * (`incoming`) never changes saved leagues: if a league already here covers
 * it, that league is selected; otherwise it comes back as `offer`. The one
 * exception is a first visit, where there is nothing saved to protect and the
 * link's setup is simply where the person starts.
 */
export function reconcile({ saved = null, incoming = null, calendarWeek }) {
  const firstVisit = !saved?.leagues?.length;
  let leagues = firstVisit ? [makeLeague()] : saved.leagues.map(makeLeague);
  let leagueId = leagues.some((l) => l.id === saved?.leagueId) ? saved.leagueId : leagues[0].id;
  let offer = null;
  if (incoming && firstVisit) {
    leagues = [makeLeague(incoming)];
    leagueId = leagues[0].id;
  } else if (incoming) {
    const here = leagues.find((l) => l.id === incoming.id && covers(l, incoming)) || leagues.find((l) => covers(l, incoming));
    if (here) leagueId = here.id;
    else offer = makeLeague(incoming);
  }
  return { leagues, leagueId, week: calendarWeek, offer };
}

/** Carry out the person's answer to an offer: 'import', 'replace' or 'ignore'. */
export function applyOffer({ leagues, leagueId }, offer, choice) {
  if (choice === 'import') {
    const added = makeLeague({ ...offer, id: leagues.some((l) => l.id === offer.id) ? newId() : offer.id });
    return { leagues: [...leagues, added], leagueId: added.id };
  }
  if (choice === 'replace') {
    return { leagues: leagues.map((l) => (l.id === leagueId ? makeLeague({ ...offer, id: l.id, name: l.name }) : l)), leagueId };
  }
  return { leagues, leagueId };
}

/**
 * Remove "Shared setup N" leagues that an earlier version created on its own
 * from page addresses. One is removed only when another league covers it, so
 * no recorded pick is lost, and the last league is never removed.
 */
export function dropAutoDuplicates({ leagues, leagueId }) {
  let kept = [...leagues];
  const removed = [];
  for (const l of leagues) {
    if (!/^Shared setup \d+$/.test(l.name) || kept.length < 2) continue;
    const keeper = kept.find((m) => m.id !== l.id && covers(m, l));
    if (!keeper) continue;
    kept = kept.filter((m) => m.id !== l.id);
    removed.push(l.id);
    if (leagueId === l.id) leagueId = keeper.id;
  }
  return { leagues: kept, leagueId, removed };
}

/* --------------------------------------------------------------------- sync */

/**
 * Merge one league that was edited in two places. `base` is the copy both
 * sides last agreed on (null if this browser never synced it).
 *
 * A setting or a week's pick changed on one side takes that side's value.
 * Changed on both, the account's copy wins. So a pick recorded on the phone
 * and a different week's pick recorded on the laptop both survive, and no
 * clock is consulted.
 */
export function merge3(base, local, remote) {
  const out = content(remote);
  if (base) {
    for (const f of SETTINGS) if (String(remote[f]) === String(base[f])) out[f] = local[f];
  }
  const used = {};
  const weeks = new Set([...Object.keys(local.used), ...Object.keys(remote.used), ...Object.keys(base?.used || {})]);
  for (const w of [...weeks].sort((a, b) => a - b)) {
    const remoteChanged = remote.used[w] !== base?.used?.[w];
    const pick = remoteChanged ? remote.used[w] : local.used[w];
    if (pick) used[w] = pick;
  }
  // A team can be used once. If the two sides spent the same team in different
  // weeks, keep the account's week for it.
  const weekOf = new Map();
  for (const [w, t] of Object.entries(used)) {
    const earlier = weekOf.get(t);
    if (earlier === undefined) { weekOf.set(t, w); continue; }
    const drop = remote.used[w] === t ? earlier : w;
    delete used[drop];
    if (drop === earlier) weekOf.set(t, w);
  }
  out.used = used;
  return out;
}

/** An account row as the sync code sees it. Rows written before revisions existed have rev null. */
export function parseRow(row) {
  const data = row.data || {};
  return { id: row.id, rev: data.rev ?? null, deleted: data.deleted === true, content: content(makeLeague({ ...data, id: row.id })) };
}

/**
 * Decide what a sync has to do, without doing it.
 *
 *   local    leagues in this browser
 *   bases    { id: { rev, content } }: the account's copy as of this browser's last sync
 *   remote   parsed account rows, including deleted ones
 *   deleted  ids deleted in this browser that the account hasn't been told about
 *
 * Returns the leagues to keep here, the writes to send, the bases those leave
 * untouched, and any offers.
 */
export function planSync({ local, bases = {}, remote, deleted = [] }) {
  const firstSync = Object.keys(bases).length === 0;
  const remoteById = new Map(remote.map((r) => [r.id, r]));
  const live = remote.filter((r) => !r.deleted);
  const pendingDelete = new Set(deleted);
  const leagues = [];
  const writes = [];
  const offers = [];
  const nextBases = {};

  for (const l of local) {
    const r = remoteById.get(l.id);
    const base = bases[l.id] || null;
    if (r?.deleted) continue;                 // deleted on another device: the delete stands
    if (r) {
      const merged = { id: l.id, ...merge3(base?.content || null, l, r.content) };
      leagues.push(merged);
      if (sameContent(merged, r.content)) nextBases[l.id] = { rev: r.rev, content: content(merged) };
      else writes.push({ type: 'update', id: l.id, expect: r.rev, content: content(merged) });
      continue;
    }
    if (base) continue;                       // it was in the account and its row is gone
    if (firstSync && live.length) {
      // This browser's first sync with an account that already has leagues: its
      // own leagues are not uploaded as extras. Anything the account already
      // covers is dropped; anything else is the person's call.
      if (!isUntouchedStarter(l) && !live.some((other) => covers(other.content, l))) offers.push(l);
      continue;
    }
    leagues.push(l);
    writes.push({ type: 'insert', id: l.id, content: content(l) });
  }

  const localIds = new Set(local.map((l) => l.id));
  for (const r of live) {
    if (localIds.has(r.id)) continue;
    if (pendingDelete.has(r.id)) { writes.push({ type: 'delete', id: r.id, expect: r.rev }); continue; }
    // Separate copies: the league will be edited in place, the base must not follow it.
    leagues.push({ id: r.id, ...content(r.content) });
    nextBases[r.id] = { rev: r.rev, content: content(r.content) };
  }
  return { leagues, writes, offers, bases: nextBases };
}

/**
 * Bring this browser and the account into agreement.
 *
 * `store` reads and writes account rows: list(), insert(id, data) and
 * update(id, data, expectedRev), where the two writes resolve to false if the
 * row is not as expected (someone else wrote first). Every write carries a new
 * revision, and an update only lands on the revision it was planned against,
 * so a write from another device is never overwritten unseen: the sync just
 * reads again and merges. Deletes are written as a tombstone so other devices
 * learn of them.
 */
export async function runSync(store, { local, bases = {}, deleted = [] }) {
  let offers = [];
  for (let attempt = 0; ; attempt++) {
    const remote = (await store.list()).map(parseRow);
    const plan = planSync({ local, bases, remote, deleted });
    offers = offers.concat(plan.offers);
    const nextBases = { ...plan.bases };
    const stillDeleted = [];
    let conflict = false;
    for (const w of plan.writes) {
      const rev = newRev();
      let ok;
      if (w.type === 'insert') ok = await store.insert(w.id, { ...w.content, rev });
      else if (w.type === 'update') ok = await store.update(w.id, { ...w.content, rev }, w.expect);
      else ok = await store.update(w.id, { deleted: true, rev }, w.expect);
      if (ok && w.type !== 'delete') nextBases[w.id] = { rev, content: w.content };
      if (!ok) {
        conflict = true;
        if (w.type === 'delete') stillDeleted.push(w.id);
        else if (bases[w.id]) nextBases[w.id] = bases[w.id];
      }
    }
    local = plan.leagues;
    bases = nextBases;
    deleted = stillDeleted;
    if (!conflict || attempt >= 2) return { leagues: local, bases, deleted, offers, settled: !conflict };
  }
}
