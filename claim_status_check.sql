-- Lets the claim modal check "does this business already have an open claim"
-- before showing the form, without exposing any requester PII to the public
-- anon key -- claim_requests' own RLS (see portal_security_and_storage.sql)
-- deliberately restricts SELECT to the claim's own owner or an admin, so a
-- plain client-side query can't be used for this. This function returns only
-- a bare status string ('pending' / 'approved' / null), nothing else.
-- Run this once in the Supabase SQL editor.

create or replace function public.claim_status_for_business(p_business_id text)
returns text
language sql security definer set search_path = public as $$
  select status from public.claim_requests
  where business_id::text = p_business_id
    and status in ('pending', 'approved')
  order by case status when 'approved' then 0 else 1 end
  limit 1;
$$;

revoke execute on function public.claim_status_for_business(text) from public;
grant execute on function public.claim_status_for_business(text) to anon, authenticated;

-- ============================================================
-- Case-insensitive owner lookup for portal.html
-- ============================================================
-- The claim form doesn't normalize email casing at submission time (see
-- claim.js), so an owner who claimed as "Info@Biz.ie" but later signs in as
-- "info@biz.ie" needs a case-insensitive match here -- a plain PostgREST
-- .eq('requester_email', ...) is case-sensitive and would silently show
-- "unauthorized" for an already-approved claim. Deliberately takes no
-- parameter and reads the caller's own JWT internally (rather than accepting
-- an arbitrary p_email argument) so it can only ever answer "is *this*
-- logged-in user an approved owner", never be used to probe other people's
-- emails for an approved business_id.
create or replace function public.my_approved_business_id()
returns text
language sql security definer set search_path = public as $$
  select business_id::text from public.claim_requests
  where lower(requester_email) = lower(auth.jwt() ->> 'email')
    and status = 'approved'
  limit 1;
$$;

revoke execute on function public.my_approved_business_id() from public;
grant execute on function public.my_approved_business_id() to authenticated;
