-- Sets up everything the owner portal needs to actually work securely:
--   1. An admins allowlist, so only specific people can approve claims (fixes a real
--      gap: previously ANY signed-up user could open admin.html and approve any claim,
--      including their own, then edit that business via the owner portal).
--   2. RLS on claim_requests so owners can see their own claim status and admins can
--      see/approve all of them (currently this table has no working policies at all,
--      which is also why "pending approval" likely never resolved for real users).
--   3. An UPDATE policy on classes so an owner with an *approved* claim for a specific
--      business can edit only that business (currently there is NO update policy at
--      all, so the portal's "Save Changes" has been silently doing nothing).
--   4. A public storage bucket + per-business-scoped storage policies for owner-
--      uploaded logo/banner images.
--
-- Run this once in the Supabase SQL editor.

-- ============================================================
-- 1. Admins allowlist
-- ============================================================
create table if not exists public.admins (
  email text primary key
);

alter table public.admins enable row level security;

create policy "Users can check their own admin status" on public.admins
  for select
  using (lower(email) = lower(auth.jwt() ->> 'email'));

insert into public.admins (email) values ('davidmacmahon1@gmail.com')
  on conflict (email) do nothing;

-- ============================================================
-- 2. claim_requests RLS
-- ============================================================
alter table public.claim_requests enable row level security;

drop policy if exists "Owners and admins can view relevant claims" on public.claim_requests;
create policy "Owners and admins can view relevant claims" on public.claim_requests
  for select
  using (
    lower(requester_email) = lower(auth.jwt() ->> 'email')
    or exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );

-- Anyone (including a not-yet-signed-up visitor) can submit a claim, but only ever
-- as 'pending' -- they cannot insert a pre-approved claim for themselves.
drop policy if exists "Anyone can submit a pending claim" on public.claim_requests;
create policy "Anyone can submit a pending claim" on public.claim_requests
  for insert
  with check (status = 'pending');

-- Only admins can change a claim's status (i.e. approve/reject).
drop policy if exists "Only admins can update claims" on public.claim_requests;
create policy "Only admins can update claims" on public.claim_requests
  for update
  using (exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email')));

-- ============================================================
-- 3. classes UPDATE policy, scoped to approved ownership
-- ============================================================
drop policy if exists "Approved owners can update their business" on public.classes;
create policy "Approved owners can update their business" on public.classes
  for update
  using (
    exists (
      select 1 from public.claim_requests cr
      where cr.business_id::text = classes.id::text
        and cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
    )
  )
  with check (
    exists (
      select 1 from public.claim_requests cr
      where cr.business_id::text = classes.id::text
        and cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
    )
  );

-- ============================================================
-- 4. Storage bucket + policies for owner-uploaded images
-- ============================================================
insert into storage.buckets (id, name, public)
values ('business-uploads', 'business-uploads', true)
on conflict (id) do nothing;

drop policy if exists "Public can view business uploads" on storage.objects;
create policy "Public can view business uploads" on storage.objects
  for select
  using (bucket_id = 'business-uploads');

drop policy if exists "Approved owners can upload their business assets" on storage.objects;
create policy "Approved owners can upload their business assets" on storage.objects
  for insert
  with check (
    bucket_id = 'business-uploads'
    and exists (
      select 1 from public.claim_requests cr
      where cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
        and cr.business_id::text = (storage.foldername(name))[1]
    )
  );

drop policy if exists "Approved owners can update their business assets" on storage.objects;
create policy "Approved owners can update their business assets" on storage.objects
  for update
  using (
    bucket_id = 'business-uploads'
    and exists (
      select 1 from public.claim_requests cr
      where cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
        and cr.business_id::text = (storage.foldername(name))[1]
    )
  );

drop policy if exists "Approved owners can delete their business assets" on storage.objects;
create policy "Approved owners can delete their business assets" on storage.objects
  for delete
  using (
    bucket_id = 'business-uploads'
    and exists (
      select 1 from public.claim_requests cr
      where cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
        and cr.business_id::text = (storage.foldername(name))[1]
    )
  );
