-- Splits individual_classes.time (a single free-text field like "10:00-10:45")
-- into separate start_time/end_time text columns -- matches the pattern already
-- used for the summary schedule on public.classes, and lets the portal's
-- Individual Classes tab collect a "From" and "To" time as distinct fields.
--
-- Run this once in the Supabase SQL editor (only needed if you already ran
-- portal_individual_classes.sql before this change). Safe to run even though
-- the table currently has no rows -- no data migration needed.

alter table public.individual_classes drop column if exists time;
alter table public.individual_classes add column if not exists start_time text;
alter table public.individual_classes add column if not exists end_time text;
