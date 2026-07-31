-- Removes pre-existing wide-open policies on claim_requests that were undermining
-- the admin-only-approval and owner-scoping just added. These were live and
-- exploitable: any signed-up user could insert a pre-approved claim directly, or
-- PATCH any existing claim to status='approved', bypassing admin.html entirely.
-- Run this once in the Supabase SQL editor.

drop policy if exists "Allow public inserts" on public.claim_requests;
drop policy if exists "Allow authenticated reads" on public.claim_requests;
drop policy if exists "Allow authenticated updates" on public.claim_requests;

-- Redundant with "Approved owners can update their business" (same intent, this one
-- just lacks the case-insensitive email match and a WITH CHECK clause) -- not a
-- security issue, just cleanup to avoid two overlapping policies drifting apart later.
drop policy if exists "Allow owners to update their class" on public.classes;
