-- Adds Google Places review data (rating, count, review snippets) to classes,
-- to replace/augment the site's own class_ratings widget (see add_ratings_table.sql)
-- with real Google reviews per business.
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).
-- Nothing in this repo can create/alter tables via the REST API, so this has to be
-- applied manually.

alter table public.classes
  add column if not exists google_place_id text,
  add column if not exists google_rating numeric,
  add column if not exists google_rating_count integer,
  add column if not exists google_maps_uri text,
  add column if not exists google_reviews jsonb,
  add column if not exists google_reviews_fetched_at timestamptz;

-- No RLS policy changes needed: classes already has a public SELECT policy
-- covering all columns (see supabase-schema.sql), and these are only ever
-- written server-side via scripts/google_places_reviews_pilot.py using the
-- service-role secret (SB_SECRET), same as latitude/longitude from
-- scripts/google_geocode_missing.py.
