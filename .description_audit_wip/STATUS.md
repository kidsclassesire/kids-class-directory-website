# Full DB audit / description rewrite — status snapshot

Paused mid-task at the user's request. This directory holds the working data needed to resume without redoing the audit or re-fetching from Supabase.

## Done and pushed
- `replace_individual_classes_time_split.sql`, `dedupe_little_kickers_locations.sql`, `dedupe_multi_class_venues.sql`, `dedupe_duplicate_import_rows.sql` — all applied live and pushed (earlier session).
- `phone_number_cleanup.sql` (repo root) — 762 phone number normalizations, ready to run in the Supabase SQL editor, NOT yet run.

## Audit findings (from this session, still valid — re-derive by re-running the queries in this dir's `all_classes_full.json` if needed, or refetch from Supabase)
- Duplicates: clean, zero remaining (company_name, address) dupes as of last check.
- Emails: clean, no structural issues found.
- URLs: totsspots.com / directory domains never appear in `website_url` or `booking_url` (only in the never-rendered `source_urls` field) — nothing to fix. The "15 redundant Facebook/Instagram website_url" finding was a FALSE ALARM on closer inspection (different pages serving different purposes) — do not action that.
- Phone numbers: `phone_number_cleanup.sql` has the fix, 762 rows, 2 rows intentionally left alone (ids 1509, 1563 — source data looks corrupted, needs manual verification with the business, not a safe auto-fix).
- Descriptions: 113 rows share verbatim text with a *different* business, 350 more reused within the same franchise, 109 are under 60 chars, and 0 of 1872 have any paragraph break (template renders description as one `<p>` block).

## Description rewrite — IN PROGRESS
User chose: full pass on all ~1872 rows, batched by franchise/chain (18 batches of ~110 rows, grouped so an agent sees all of a chain's locations at once to differentiate them), one background agent per batch, each writing `desc_out/batch_NN.json` (array of `{id, description}` with `\n\n` paragraph breaks).

**Completed and QA'd (6 of 18 batches, 556 of 1872 rows):** batch_00, batch_02, batch_05, batch_12, batch_13, batch_17 — all in `desc_out/`. QA passed: 0 duplicates, 0 too-short, 0 too-long, 0 leftover placeholders, ids match. **Known issue: 65 of these 556 rows have no `\n\n` paragraph break** (agent didn't follow the format rule) — re-check/fix before final SQL generation. Get the list via the QA script below.

**Not done (12 of 18 batches, 1316 of 1872 rows):** batch_01, batch_03, batch_04, batch_06, batch_07, batch_08, batch_09, batch_10, batch_11, batch_14, batch_15, batch_16. All failed either from hitting the session usage limit or were stopped intentionally. Input data for these is already split and waiting in `desc_batches/batch_NN.json` — just needs the same agent prompt re-run against each (see below).

## To resume
1. Re-launch background agents for the 12 missing batches. Use the exact prompt template from this session (batch number + `desc_batches/batch_NN.json` in, `desc_out/batch_NN.json` out — same rules: never invent business-specific facts, differentiate franchise siblings, 2-4 short paragraphs separated by `\n\n`, correct grammar, ~350-700 chars). Consider smaller batches (~50-60 rows) if session limits are a recurring problem — smaller batches finished more reliably last time (batch_17 at 17 rows and batch_00 at 101 rows both succeeded; several 110-row batches got cut off).
2. Once all 18 land, run the QA/compile script (recreate from this file's logic, or rebuild it: load every `desc_out/batch_NN.json`, verify one entry per id in `all_classes_full.json`, check for `\n\n`, check length sanity, check for accidental leftover duplicate text, check the 65 already-flagged no-paragraph-break rows).
3. Generate the final `description_cleanup.sql`: one `update public.classes set description = '...' where id = N;` per row, wrapped in `begin`/`commit` like the other migration files, watching apostrophe escaping (`''`).
4. Apply the template change to `scripts/generate_business_pages.py` (NOT yet applied — still just specced in this conversation):
   - `meta_description()`: collapse `\n\n`/whitespace to single spaces before the 160-char truncation.
   - `json_ld()`: same whitespace collapse for both `ld['description']` and `course['description']`.
   - The `<p class="description">{esc(row.get("description"))}</p>` line (~line 524): replace with a helper that splits on `\n\n` and renders one `<p class="description" style="-webkit-line-clamp: unset;">` per paragraph.
5. After the user runs `description_cleanup.sql` in Supabase: regenerate pages (`generate_business_pages.py && generate_landing_pages.py`), commit, push — same workflow as every other DB change this session.
6. Once everything's applied, delete this `.description_audit_wip/` directory (it's scratch, not meant to ship).
