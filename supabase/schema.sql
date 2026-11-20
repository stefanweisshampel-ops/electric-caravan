-- =====================================================================
-- Gespann-Lader – Datenbank-Schema für Supabase
-- Einmal komplett im SQL-Editor von Supabase ausführen.
-- =====================================================================

-- ---------- Bewertungen: eine pro Person und Standort -----------------
create table if not exists public.ratings (
  id          uuid primary key default gen_random_uuid(),
  site_key    text not null check (char_length(site_key) between 5 and 40
                                   and site_key ~ '^[A-Z]{2}-[-0-9.]+_[-0-9.]+$'),
  country     text not null check (country ~ '^[A-Z]{2}$'),
  lat         double precision not null check (lat between -90 and 90),
  lon         double precision not null check (lon between -180 and 180),
  status      text not null check (status in ('ja', 'eng', 'nein')),
  note        text not null default '' check (char_length(note) <= 300),
  site_name   text not null default '' check (char_length(site_name) <= 120),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (site_key, user_id)
);
create index if not exists ratings_site_idx on public.ratings (site_key);
create index if not exists ratings_country_idx on public.ratings (country);

create or replace function public.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists ratings_touch on public.ratings;
create trigger ratings_touch before update on public.ratings
  for each row execute function public.touch_updated_at();

-- Zugriffsregeln: Jede Person sieht und ändert direkt nur ihre eigenen Zeilen.
-- Alle anderen sehen Bewertungen nur anonym über die Funktionen unten.
alter table public.ratings enable row level security;

drop policy if exists "eigene lesen" on public.ratings;
create policy "eigene lesen" on public.ratings
  for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "eigene anlegen" on public.ratings;
create policy "eigene anlegen" on public.ratings
  for insert to authenticated with check (user_id = (select auth.uid()));
drop policy if exists "eigene ändern" on public.ratings;
create policy "eigene ändern" on public.ratings
  for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "eigene löschen" on public.ratings;
create policy "eigene löschen" on public.ratings
  for delete to authenticated using (user_id = (select auth.uid()));

-- ---------- Öffentliche, anonyme Sicht auf die Bewertungen -------------
-- Zusammenfassung pro Standort für die Karte (ohne Personenbezug).
create or replace function public.site_stats(p_country text default null)
returns table (site_key text, lat double precision, lon double precision,
               n_ja int, n_eng int, n_nein int, last_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select r.site_key,
         avg(r.lat), avg(r.lon),
         count(*) filter (where r.status = 'ja')::int,
         count(*) filter (where r.status = 'eng')::int,
         count(*) filter (where r.status = 'nein')::int,
         max(r.updated_at)
  from public.ratings r
  where p_country is null or r.country = p_country
  group by r.site_key
$$;

-- Einzelne Bewertungen eines Standorts (ohne Personenbezug, eigene markiert).
create or replace function public.site_ratings(p_site_key text)
returns table (status text, note text, updated_at timestamptz, is_mine boolean)
language sql stable security definer set search_path = '' as $$
  select r.status, r.note, r.updated_at, (r.user_id = auth.uid())
  from public.ratings r
  where r.site_key = p_site_key
  order by r.updated_at desc
  limit 50
$$;

revoke all on function public.site_stats(text) from public;
revoke all on function public.site_ratings(text) from public;
grant execute on function public.site_stats(text) to anon, authenticated;
grant execute on function public.site_ratings(text) to anon, authenticated;

-- ---------- Meldungen (falsche oder unpassende Bewertungen) ------------
create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  site_key    text not null check (char_length(site_key) <= 40),
  reason      text not null default '' check (char_length(reason) <= 500),
  reporter    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now()
);
alter table public.reports enable row level security;
drop policy if exists "melden" on public.reports;
create policy "melden" on public.reports
  for insert to authenticated with check (reporter = (select auth.uid()));
-- Lesen nur im Supabase-Dashboard (keine Lese-Regel = niemand außer Admin).

-- ---------- Rechte für die Daten-API (ausdrücklich gesetzt) -------------
revoke all on public.ratings, public.reports from anon;
grant select, insert, update, delete on public.ratings to authenticated;
grant insert on public.reports to authenticated;
