-- Adds logo/image path columns to classes, for the logo-fetching pipeline's output.
-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query).

alter table public.classes
  add column if not exists logo_path text,
  add column if not exists hosted_image_path text;
