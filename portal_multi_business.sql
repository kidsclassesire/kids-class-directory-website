-- Lets an owner who has more than one *approved* claim (e.g. runs several
-- venues) manage all of them from portal.html, instead of only ever seeing
-- the single oldest one. Replaces my_approved_business_id() (claim_status_check.sql),
-- which used `limit 1` and silently hid every other approved business the
-- same email owns.
--
-- The classes UPDATE policy (portal_security_and_storage.sql) already checks
-- per-business ownership via an EXISTS subquery against claim_requests, not
-- against this function, so no RLS changes are needed here -- an owner could
-- already edit any business they have an approved claim for, portal.html
-- just never asked for more than one id.
--
-- Run this once in the Supabase SQL editor.

drop function if exists public.my_approved_business_id();

create or replace function public.my_approved_business_ids()
returns setof text
language sql security definer set search_path = public as $$
  select business_id::text from public.claim_requests
  where lower(requester_email) = lower(auth.jwt() ->> 'email')
    and status = 'approved';
$$;

revoke execute on function public.my_approved_business_ids() from public;
grant execute on function public.my_approved_business_ids() to authenticated;
