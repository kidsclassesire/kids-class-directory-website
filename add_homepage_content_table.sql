-- Makes the homepage's "How Kids Patch works" section (index.html) editable
-- from admin.html instead of hardcoded in the page source. Single-row table
-- (id is fixed at 1) since there's only ever one homepage to edit -- same
-- "singleton settings row" shape as e.g. a site-config table, just scoped to
-- this one section for now.
--
-- Run this once in the Supabase SQL editor.

create table if not exists public.homepage_content (
  id integer primary key default 1,
  heading text not null default 'How Kids Patch works',
  intro text not null default '',
  step1_title text not null default '',
  step1_description text not null default '',
  step2_title text not null default '',
  step2_description text not null default '',
  step3_title text not null default '',
  step3_description text not null default '',
  updated_at timestamptz not null default now(),
  constraint homepage_content_singleton check (id = 1)
);

-- Seeded with the exact copy already shipped in index.html, so running this
-- migration doesn't change anything visible until an admin actually edits it.
insert into public.homepage_content (
  id, heading, intro,
  step1_title, step1_description,
  step2_title, step2_description,
  step3_title, step3_description
) values (
  1,
  'How Kids Patch works',
  'Kids Patch is Ireland''s directory of children''s classes and activities — swimming, GAA, dance, coding, art and everything in between. We bring together activities from local providers in every county so parents can compare schedules, ages and pricing in one place, then reach out directly. No accounts, no booking fees, no middleman.',
  'Search & compare',
  'Filter by category, age, location, price or day, and see everything side by side — no more digging through a dozen different websites.',
  'Contact the provider directly',
  'Message a provider straight from their listing, or visit their website — whichever''s easier. Your enquiry goes straight to them, not to us.',
  'Get your child started',
  'Confirm a spot directly with the provider. It''s free for parents to use Kids Patch, always.'
)
on conflict (id) do nothing;

alter table public.homepage_content enable row level security;

-- The homepage itself reads this with the public anon key, so anyone can
-- read it -- same as `classes`.
drop policy if exists "Anyone can read homepage content" on public.homepage_content;
create policy "Anyone can read homepage content" on public.homepage_content
  for select
  using (true);

drop policy if exists "Only admins can edit homepage content" on public.homepage_content;
create policy "Only admins can edit homepage content" on public.homepage_content
  for update
  using (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')))
  with check (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));
