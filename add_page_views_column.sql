-- Adds a rolling 30-day page-view counter to classes, for
-- scripts/fetch_ga4_pageviews.py -- refreshed nightly from GA4, displayed to
-- the owner in portal.html. Not a lifetime total: each nightly run overwrites
-- it with the current trailing-30-day GA4 count for that business page.
-- Left NULL (no default) until the first nightly run, deliberately -- that's
-- how portal.html tells "never computed yet" apart from "computed, genuinely
-- zero views".
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

alter table public.classes
  add column if not exists page_views_30d integer;
