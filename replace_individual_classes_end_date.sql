-- Swaps individual_classes.end_date for duration_weeks -- an owner setting up a
-- class knows how many weeks it runs far more often than the exact end date, and
-- duration_weeks is what the portal's Individual Classes tab now collects.
--
-- Run this once in the Supabase SQL editor (only needed if you already ran
-- portal_individual_classes.sql before this change).

alter table public.individual_classes drop column if exists end_date;
alter table public.individual_classes add column if not exists duration_weeks integer;
