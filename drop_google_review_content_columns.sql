-- Reverts the review-content columns added by add_google_reviews_columns.sql.
-- Decision: storing rating/review text/count long-term and baking it into static
-- pages isn't compliant with the Places API terms (only place_id may be cached
-- indefinitely -- everything else is meant to be requested live, not warehoused:
-- https://developers.google.com/maps/documentation/places/web-service/policies).
-- Reverting to the site's own class_ratings widget (add_ratings_table.sql) instead.
--
-- google_place_id is kept -- it's the one field Google's terms permit storing
-- indefinitely, and it may be useful for a future live-fetch (not stored) review
-- display, or other Place Details lookups.
--
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

alter table public.classes
  drop column if exists google_rating,
  drop column if exists google_rating_count,
  drop column if exists google_maps_uri,
  drop column if exists google_reviews,
  drop column if exists google_reviews_fetched_at;
