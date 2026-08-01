-- Admin console upgrade: lets admins manage the admins allowlist itself from
-- the UI (not just via the SQL editor), and delete a business outright.
-- Run this once in the Supabase SQL editor.

-- ============================================================
-- 0. Helper functions (SECURITY DEFINER) -- avoids a real Postgres RLS
--    self-reference bug: a policy ON admins that queries admins via a plain
--    `exists (select 1 from public.admins ...)` throws "42P17: infinite
--    recursion detected in policy for relation admins", because the subquery
--    re-triggers RLS on the same table, which re-triggers the same policy.
--    Not needed for the existing admins-checks-on-OTHER-tables policies
--    (classes/claim_requests/storage) -- those aren't self-referential.
-- ============================================================
create or replace function public.is_admin() returns boolean
language sql security definer set search_path = public as $$
  select exists (
    select 1 from public.admins where lower(email) = lower(auth.jwt() ->> 'email')
  );
$$;
revoke execute on function public.is_admin() from public;
grant execute on function public.is_admin() to authenticated;

create or replace function public.admin_count() returns integer
language sql security definer set search_path = public as $$
  select count(*)::int from public.admins;
$$;
revoke execute on function public.admin_count() from public;
grant execute on function public.admin_count() to authenticated;

-- ============================================================
-- 1. admins table: admin-wide SELECT/INSERT/DELETE
-- ============================================================
alter table public.admins add column if not exists created_at timestamptz not null default now();

-- Additive: ORs with the existing "own row only" SELECT policy, doesn't
-- replace it -- an admin can now also see every other admin's row.
drop policy if exists "Admins can view all admins" on public.admins;
create policy "Admins can view all admins" on public.admins
  for select
  using (public.is_admin());

drop policy if exists "Admins can add admins" on public.admins;
create policy "Admins can add admins" on public.admins
  for insert
  with check (public.is_admin());

-- Server-side lockout guard: blocks deleting the very last admin row, even if
-- a client-side check were somehow bypassed. Deliberately does NOT also block
-- "removing yourself while others exist" server-side -- that's a mild
-- inconvenience (re-addable by another admin), not a real lockout risk, so
-- it's left as a client-side warning only.
drop policy if exists "Admins can remove admins" on public.admins;
create policy "Admins can remove admins" on public.admins
  for delete
  using (public.is_admin() and public.admin_count() > 1);

-- ============================================================
-- 2. classes: admin-wide DELETE
-- ============================================================
-- Additive alongside the existing owner-scoped/admin-scoped UPDATE policies;
-- this is a new command (DELETE) so there's nothing to OR against yet.
drop policy if exists "Admins can delete any business" on public.classes;
create policy "Admins can delete any business" on public.classes
  for delete
  using (
    exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );

-- ============================================================
-- 3. claim_requests: rejecting a claim needs NO new policy
-- ============================================================
-- "Only admins can update claims" (see portal_security_and_storage.sql) is a
-- blanket `for update using (exists admins-check)` with no `with check`
-- constraining which status values are allowed (unlike the INSERT policy,
-- which does restrict to status = 'pending'). An admin UPDATE setting
-- status = 'rejected' is therefore already permitted by RLS as-is.
-- CAVEAT: claim_requests' own `create table` isn't tracked in any repo SQL
-- file, so a live CHECK constraint on the `status` column enumerating
-- allowed values can't be ruled out from static inspection alone. Verify with
-- one real UPDATE to status='rejected' before trusting the Reject button in
-- production -- if it errors with a check-constraint violation (not an RLS
-- 42501), that's an `alter table claim_requests drop constraint ...` /
-- `add constraint ... check (status in (...))` fix, not an RLS fix.

-- ============================================================
-- 4. Audit after running -- confirm exactly the expected policies exist
-- ============================================================
-- select * from pg_policies where schemaname = 'public' and tablename = 'admins';
-- select * from pg_policies where schemaname = 'public' and tablename = 'classes' and policyname ilike '%delete%';
