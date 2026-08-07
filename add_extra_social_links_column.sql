-- Adds an extra_social_links column to classes, for platforms beyond
-- Facebook/Instagram (which stay as their own dedicated facebook_url/
-- instagram_url columns -- see add_social_link_columns.sql -- since those are
-- read/written by scripts/scrape_social_links_safe.py, google_enrich_links.py,
-- and cleanup_bad_social_links.py; this new column is untouched by that
-- pipeline and is only ever written by the owner portal (portal.html).
--
-- Shape: a jsonb array of {"platform": "tiktok"|"youtube"|"x"|"whatsapp"|"other",
-- "url": "...", "label": "..."} objects -- "label" only present when
-- platform is "other". Rendered on the public business page by
-- scripts/generate_business_pages.py (social_widget_html).
--
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

alter table public.classes
  add column if not exists extra_social_links jsonb not null default '[]'::jsonb;
