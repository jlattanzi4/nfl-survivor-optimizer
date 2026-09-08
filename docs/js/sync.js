/**
 * Cross-device sync via Supabase (magic-link email sign-in).
 *
 * Local-first: the browser's copy is always usable. When signed in, every
 * league is upserted to `survivor_leagues` shortly after it changes, and on
 * sign-in / tab focus the remote copy is merged in by `updatedAt`.
 */
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';

const TABLE = 'survivor_leagues';
let client = null;
let listeners = [];
let saveTimer = null;
let pendingIds = new Set();
let status = 'off';   // off | signed-out | saving | synced | error

export const enabled = () => Boolean(client);
export const getStatus = () => status;
function setStatus(s) { status = s; for (const fn of listeners) fn(s); }
export const onStatus = (fn) => { listeners.push(fn); };

export function init() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !window.supabase) return false;
  client = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  setStatus('signed-out');
  return true;
}

export async function session() {
  if (!client) return null;
  const { data } = await client.auth.getSession();
  return data.session || null;
}

export function onAuth(fn) {
  if (!client) return;
  client.auth.onAuthStateChange((event, s) => fn(event, s));
}

export async function sendMagicLink(email) {
  const redirect = `${location.origin}${location.pathname}`;
  const { error } = await client.auth.signInWithOtp({ email, options: { emailRedirectTo: redirect } });
  if (error) throw error;
}

export async function signOut() {
  await client.auth.signOut();
  setStatus('signed-out');
}

const stripLocal = (l) => { const { updatedAt, ...rest } = l; return rest; };

/** Merge remote rows into local leagues. Returns the merged list and ids that need pushing. */
export async function pull(localLeagues) {
  const { data, error } = await client.from(TABLE).select('id, data, updated_at');
  if (error) throw error;
  const remote = new Map(data.map((r) => [r.id, { ...r.data, id: r.id, updatedAt: r.updated_at }]));
  const merged = [];
  const toPush = [];
  const seen = new Set();
  for (const l of localLeagues) {
    seen.add(l.id);
    const r = remote.get(l.id);
    if (!r) {
      if (isUntouchedDefault(l) && remote.size) continue;   // drop the empty starter league when the account already has leagues
      merged.push(l); toPush.push(l.id);
    } else if (new Date(l.updatedAt || 0) > new Date(r.updatedAt)) {
      merged.push(l); toPush.push(l.id);
    } else {
      merged.push(r);
    }
  }
  for (const [id, r] of remote) if (!seen.has(id)) merged.push(r);
  return { merged, toPush };
}

function isUntouchedDefault(l) {
  return l.name === 'My pool' && l.pool === 50 && l.lives === 1 && Object.keys(l.used || {}).length === 0;
}

export async function push(leagues) {
  if (!leagues.length) return;
  const rows = leagues.map((l) => ({ id: l.id, data: stripLocal(l), updated_at: l.updatedAt || new Date().toISOString() }));
  const { error } = await client.from(TABLE).upsert(rows, { onConflict: 'user_id,id' });
  if (error) throw error;
}

export async function remove(id) {
  const { error } = await client.from(TABLE).delete().eq('id', id);
  if (error) throw error;
}

/** Debounced save of changed leagues; `getLeagues` is called at flush time. */
export function scheduleSave(ids, getLeagues) {
  if (!client) return;
  for (const id of ids) pendingIds.add(id);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const s = await session();
    if (!s) return;
    const ids = [...pendingIds];
    pendingIds = new Set();
    const rows = getLeagues().filter((l) => ids.includes(l.id));
    try { setStatus('saving'); await push(rows); setStatus('synced'); }
    catch (err) { console.error('sync push failed', err); setStatus('error'); }
  }, 800);
}
