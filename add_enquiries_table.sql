-- "Message Provider" / "Request Info" form (see enquiry.js) -- lets a parent
-- send an enquiry straight from a business's listing page. Stored here (not
-- just emailed) so: (a) the Apps Script email step (gmail_notifications.gs)
-- can verify a submission is real before it will send mail on our behalf --
-- same anti-open-relay pattern as claim_requests, see portal_security_and_storage.sql
-- -- and (b) a claimed owner or admin can see their own enquiry history/count
-- later as a concrete "Kids Patch already sends you customers" trust signal.
--
-- Run this once in the Supabase SQL editor.

create table if not exists public.enquiries (
  id bigint generated always as identity primary key,
  business_id bigint not null references public.classes(id) on delete cascade,
  business_name text,
  parent_name text not null,
  parent_email text not null,
  parent_phone text,
  message text not null,
  created_at timestamptz not null default now(),
  -- Client-generated (enquiry.js: crypto.randomUUID()) and sent alongside
  -- the notify.js fetch so gmail_notifications.gs can look up this exact
  -- row via the service role key. Needed because the anon insert can't be
  -- combined with .select() to read the row straight back -- the SELECT
  -- policy below deliberately restricts reads to the business's owner/admin,
  -- not the anonymous submitter, so PII (message/email/phone) isn't
  -- queryable by anyone who can guess a business_id.
  token text not null,
  -- Set true by gmail_notifications.gs (via the service role key, which
  -- bypasses RLS) once it has actually emailed the business, so a replayed
  -- POST of the same token can't be used to spam the business's inbox.
  notified boolean not null default false
);

create index if not exists enquiries_business_id_idx on public.enquiries(business_id);
create unique index if not exists enquiries_token_idx on public.enquiries(token);

alter table public.enquiries enable row level security;

-- Anyone (including a not-yet-signed-up visitor) can submit an enquiry.
drop policy if exists "Anyone can submit an enquiry" on public.enquiries;
create policy "Anyone can submit an enquiry" on public.enquiries
  for insert
  with check (true);

-- Only the claimed+approved owner of that business, or an admin, can read
-- the enquiries -- same shape as the classes UPDATE policy in
-- portal_security_and_storage.sql.
drop policy if exists "Owners and admins can view their business enquiries" on public.enquiries;
create policy "Owners and admins can view their business enquiries" on public.enquiries
  for select
  using (
    exists (
      select 1 from public.claim_requests cr
      where cr.business_id::text = enquiries.business_id::text
        and cr.status = 'approved'
        and lower(cr.requester_email) = lower(auth.jwt() ->> 'email')
    )
    or exists (select 1 from public.admins a where lower(a.email) = lower(auth.jwt() ->> 'email'))
  );

-- No update/delete policy for anon/authenticated -- the `notified` flag is
-- only ever flipped by gmail_notifications.gs using the service role key,
-- which bypasses RLS entirely.
