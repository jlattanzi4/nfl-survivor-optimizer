-- Survivor: per-user league storage. Paste into the Supabase SQL editor once.
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
