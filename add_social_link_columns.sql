-- Adds Facebook/Instagram link columns to classes, for scripts/google_enrich_links.py.
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

alter table public.classes
  add column if not exists facebook_url text,
  add column if not exists instagram_url text;
