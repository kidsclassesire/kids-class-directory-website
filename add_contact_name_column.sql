-- Adds a contact_name column so an owner can list a named contact for their
-- business, alongside the existing email_address/phone_number fields.
--
-- Run this once in the Supabase SQL editor.

alter table public.classes add column if not exists contact_name text;
