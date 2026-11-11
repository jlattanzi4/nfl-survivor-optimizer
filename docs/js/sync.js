/**
 * Cross-device sync via Supabase (magic-link email sign-in).
 *
 * The browser's copy is always usable on its own. When signed in, the account
 * is the copy every device agrees with: each sync reads it, merges this
 * browser's edits into it (leagues.js decides how), and writes back only what
 * changed. Writes are guarded by a revision, so two devices can't silently
 * overwrite each other, and deletes are kept as tombstones so they travel.
 */
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';
import { runSync } from './leagues.js';

const TABLE = 'survivor_leagues';
const SAVE_DELAY_MS = 800;
let client = null;
let listeners = [];
let status = 'off';   // off | signed-out | saving | synced | error
let hooks = null;     // { read(): { local, bases, deleted }, write(result, before) }
let timer = null;
let running = null;
let again = false;
let leaving = false;  // the page is being hidden: let requests outlive it

export const enabled = () => Boolean(client);
export const getStatus = () => status;
function setStatus(s) { status = s; for (const fn of listeners) fn(s); }
export const onStatus = (fn) => { listeners.push(fn); };

export function init() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !window.supabase) return false;
  client = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    global: { fetch: (input, init = {}) => fetch(input, leaving ? { ...init, keepalive: true } : init) },
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

/** The account's table, behind the three calls runSync needs. */
function accountStore() {
  const stamp = () => new Date().toISOString();   // for people reading the table; never used to merge
  return {
    async list() {
      const { data, error } = await client.from(TABLE).select('id, data');
      if (error) throw error;
      return data;
    },
    async insert(id, data) {
      const { error } = await client.from(TABLE).insert({ id, data: { ...data, id }, updated_at: stamp() });
      if (error?.code === '23505') return false;   // the id already exists: read again and merge
      if (error) throw error;
      return true;
    },
    async update(id, data, expectedRev) {
      const write = client.from(TABLE).update({ data: { ...data, id }, updated_at: stamp() }).eq('id', id);
      const guarded = expectedRev === null ? write.is('data->>rev', null) : write.eq('data->>rev', expectedRev);
      const { data: rows, error } = await guarded.select('id');
      if (error) throw error;
      return rows.length === 1;
    },
  };
}

/** Tell sync how to read this browser's leagues and how to hand back the result. */
export function connect(h) { hooks = h; }

/** Sync shortly, once edits settle. With the page on its way out there is no waiting. */
export function schedule(delay = SAVE_DELAY_MS) {
  if (!client || !hooks) return;
  clearTimeout(timer);
  timer = setTimeout(now, leaving ? 0 : delay);
}

/** Sync now. A call made while a sync is running becomes one follow-up run. */
export function now() {
  clearTimeout(timer);
  timer = null;
  if (!client || !hooks) return Promise.resolve();
  if (running) { again = true; return running; }
  running = (async () => {
    try {
      do {
        again = false;
        if (!(await session())) return;
        setStatus('saving');
        const before = hooks.read();
        const result = await runSync(accountStore(), before);
        hooks.write(result, before);
        setStatus(result.settled ? 'synced' : 'error');
      } while (again);
    } catch (err) {
      console.error('sync failed', err);
      setStatus('error');
    } finally {
      running = null;
    }
  })();
  return running;
}

/**
 * The page is being hidden (tab switch, app switch, close). Send any edit
 * still waiting on the save delay, and let the requests finish without the page.
 */
export function leave() {
  leaving = true;
  if (timer !== null) now();
}

/** The page is visible again: pick up whatever other devices did meanwhile. */
export function comeBack() {
  leaving = false;
  return now();
}
