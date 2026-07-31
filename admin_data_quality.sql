-- Supports the new "Data Quality Review" section in admin.html: lets an admin
-- browse and fix flagged rows (dead website links, missing coordinates, missing
-- images) directly, without me running one-off scripts/SQL each time.
--
-- Run this once in the Supabase SQL editor.

-- ============================================================
-- 1. New columns on classes
-- ============================================================
alter table public.classes
  -- link-check results, written by scripts/refresh_website_status.py (service-role key)
  add column if not exists website_status text,
  add column if not exists website_checked_at timestamptz,

  -- per-flag-type dismiss/ignore, set only by an admin from the review page
  add column if not exists website_flag_dismissed boolean not null default false,
  add column if not exists website_flag_dismissed_at timestamptz,

  add column if not exists coords_flag_dismissed boolean not null default false,
  add column if not exists coords_flag_dismissed_at timestamptz,

  add column if not exists image_flag_dismissed boolean not null default false,
  add column if not exists image_flag_dismissed_at timestamptz;

-- ============================================================
-- 2. Admin-wide UPDATE policy on classes
-- ============================================================
-- This is a second PERMISSIVE policy for UPDATE, alongside the existing
-- "Approved owners can update their business" policy -- Postgres ORs them, so this
-- only ADDS admin access on top of what owners already have; it cannot loosen the
-- owner policy or grant anything to a non-admin (same admins-table EXISTS gate
-- already proven safe for claim_requests).
drop policy if exists "Admins can update any business" on public.classes;
create policy "Admins can update any business" on public.classes
  for update
  using (
    exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  )
  with check (
    exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );

-- ============================================================
-- 3. Admin-wide storage.objects policy for business-uploads
-- ============================================================
-- No folder scoping (unlike the owner-scoped policies) since an admin must be able
-- to write into ANY business's folder, including unclaimed businesses with no
-- claim_requests row at all -- which is most of the flagged "missing image" rows.
drop policy if exists "Admins can manage any business assets" on storage.objects;
create policy "Admins can manage any business assets" on storage.objects
  for all
  using (
    bucket_id = 'business-uploads'
    and exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  )
  with check (
    bucket_id = 'business-uploads'
    and exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );

-- ============================================================
-- 4. Audit after running -- confirm exactly the expected policies exist
-- ============================================================
-- select * from pg_policies where schemaname = 'public' and tablename = 'classes';
-- select * from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname ilike '%business%';
