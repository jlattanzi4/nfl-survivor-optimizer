-- Survivor: per-user league storage. Paste into the Supabase SQL editor once.
--
-- `data` holds one league: name, pool, lives, fieldStrikes, myStrikes, used
-- ({ week: team }), plus two fields the sync relies on:
--   rev      a new random value on every write. An update only lands on the
--            revision it was planned against (docs/js/sync.js), so a write from
--            another device is never overwritten unseen.
--   deleted  true for a tombstone: the league was deleted, and the row stays so
--            other devices learn of it.
-- `updated_at` is set by the client for people reading the table. It is not
-- used to merge.
create table if not exists public.survivor_leagues (
  id         text        not null,
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  data       jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);

alter table public.survivor_leagues enable row level security;

drop policy if exists "own leagues" on public.survivor_leagues;
create policy "own leagues" on public.survivor_leagues
  for all to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
