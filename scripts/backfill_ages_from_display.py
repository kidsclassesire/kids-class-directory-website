"""Backfill public.classes.minimum_age/maximum_age by parsing age_range_display,
for rows where both numeric age fields are still null but age_range_display has
a confidently-parseable value. Never overwrites an existing minimum_age or
maximum_age -- only ever fills the two columns when both are null.

age_range_display turns out to be machine-generated, not free text: almost
every value is a comma-separated enumeration of tokens like "3 year old" or
"0-6 months" (a small minority are genuinely unstructured, e.g. "Toddlers-adult"
or "Squad-based: Sharks (entry)" -- those are left alone). Only three token
shapes are recognized (see parse_age_range_display) -- anything else, or an
enumeration with a real gap in it (e.g. "0-6 months, 15 year old", which would
falsely claim coverage of every age in between if collapsed into one range),
is skipped and written to SKIPPED_DST for manual review rather than guessed at.

Run:
  python3 scripts/backfill_ages_from_display.py --dry-run
  SB_SECRET=... python3 scripts/backfill_ages_from_display.py --confirm
"""

import argparse
import json
import os
import re
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
# Same publishable/anon key already shipped in index.html/portal.html -- fine to
# read with (RLS grants public SELECT on classes), so --dry-run works without
# needing SB_SECRET at all. Writing still requires SB_SECRET (a service-role
# key), same as scripts/google_enrich_links.py.
PUBLIC_ANON_KEY = 'sb_publishable_eduvbMySPxHPT0iZjE_LqQ_w6nyjnjY'

AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/age_backfill_audit.json'
SKIPPED_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/age_backfill_skipped.json'

PAGE_SIZE = 1000  # PostgREST caps a single response at this regardless of the Range requested

YEAR_OLD = re.compile(r'^(\d+)\s*years?\s*old$', re.I)
MONTHS_RANGE = re.compile(r'^(\d+)\s*-\s*(\d+)\s*months?$', re.I)
BARE_RANGE = re.compile(r'^(\d+)\s*-\s*(\d+)$')


def parse_age_range_display(text):
    """Returns (minimum_age, maximum_age) if `text` parses confidently into a
    single contiguous numeric range, else None.

    Recognizes only: "N year(s) old", "N-M months", and a bare "N-M" (read as
    years). Splits on commas first -- age_range_display is usually a list of
    such tokens, e.g. "0-6 months, 6-12 months, 1 year old, 2 year old".
    """
    tokens = [t.strip() for t in text.split(',') if t.strip()]
    if not tokens:
        return None

    parsed = []
    for tok in tokens:
        m = YEAR_OLD.match(tok)
        if m:
            parsed.append(('year', int(m.group(1))))
            continue
        m = MONTHS_RANGE.match(tok)
        if m:
            parsed.append(('months', int(m.group(1)), int(m.group(2))))
            continue
        m = BARE_RANGE.match(tok)
        if m:
            parsed.append(('bare', int(m.group(1)), int(m.group(2))))
            continue
        return None  # unrecognized token -- don't guess at this row

    los, his, years_covered = [], [], set()
    for item in parsed:
        if item[0] == 'year':
            n = item[1]
            los.append(n)
            his.append(n)
            years_covered.add(n)
        elif item[0] == 'months':
            lo_m, hi_m = item[1], item[2]
            los.append(lo_m / 12)
            his.append(hi_m / 12)
            years_covered.add(0)
        else:  # 'bare'
            lo, hi = item[1], item[2]
            los.append(lo)
            his.append(hi)
            years_covered.update(range(lo, hi + 1))

    # Reject an enumeration with a real gap -- e.g. "0-6 months, 15 year old"
    # (a baby/teen programme with nothing in between) would otherwise collapse
    # into a misleading minimum_age=0, maximum_age=15.
    if len(years_covered) >= 2:
        span = max(years_covered) - min(years_covered) + 1
        if span != len(years_covered):
            return None

    return (round(min(los), 2), round(max(his), 2))


def sb_headers(key):
    return {'apikey': key, 'Authorization': f'Bearer {key}'}


def fetch_candidate_rows(read_key):
    headers = sb_headers(read_key)
    url = (
        f'{SUPABASE_URL}/rest/v1/classes'
        '?select=id,company_name,age_range_display'
        '&minimum_age=is.null&maximum_age=is.null&age_range_display=not.is.null'
        '&order=id'
    )
    rows = []
    offset = 0
    while True:
        req = urllib.request.Request(
            url, headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + PAGE_SIZE - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.loads(resp.read())
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def patch_row(secret, row_id, updates):
    headers = {**sb_headers(secret), 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}',
        data=json.dumps(updates).encode(), headers=headers, method='PATCH',
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--confirm', action='store_true')
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    secret = os.environ.get('SB_SECRET')
    rows = fetch_candidate_rows(secret or PUBLIC_ANON_KEY)
    if args.limit:
        rows = rows[:args.limit]
    print(f'{len(rows)} rows have no minimum_age/maximum_age but do have an age_range_display.')

    to_write = []
    skipped = []
    for row in rows:
        result = parse_age_range_display(row['age_range_display'])
        if result is None:
            skipped.append(row)
        else:
            min_age, max_age = result
            to_write.append((row, min_age, max_age))

    print(f'Confidently parseable: {len(to_write)}')
    print(f'Left for manual review (unrecognized token or gapped enumeration): {len(skipped)}')

    os.makedirs(os.path.dirname(SKIPPED_DST), exist_ok=True)
    with open(SKIPPED_DST, 'w') as f:
        json.dump(skipped, f, indent=2)
    print(f'Skipped rows written to {SKIPPED_DST} for review.')

    print('\nSample of what would be written:')
    for row, min_age, max_age in to_write[:15]:
        print(f'  id={row["id"]:<6} minimum_age={min_age:<6} maximum_age={max_age:<6}  '
              f'({row["company_name"]!r} <- {row["age_range_display"]!r})')
    if len(to_write) > 15:
        print(f'  ... and {len(to_write) - 15} more')

    if args.dry_run:
        print('\n--dry-run: no DB writes made.')
        return
    if not args.confirm:
        print('\nRefusing to run without --confirm (this writes to the live DB).')
        return
    if not secret:
        raise SystemExit('SB_SECRET is not set (required to write -- the public anon key is read-only).')

    audit = []
    written = 0
    for i, (row, min_age, max_age) in enumerate(to_write):
        updates = {'minimum_age': min_age, 'maximum_age': max_age}
        try:
            patch_row(secret, row['id'], updates)
            written += 1
            audit.append({'id': row['id'], 'company_name': row['company_name'],
                           'age_range_display': row['age_range_display'], **updates})
            print(f'[{i + 1}/{len(to_write)}] Updated id={row["id"]} ({row["company_name"]}): {updates}')
        except Exception as e:
            print(f'[{i + 1}/{len(to_write)}] FAILED to write id={row["id"]}: {e}')

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'\nWrote updates for {written}/{len(to_write)} rows.')
    print(f'Audit log: {AUDIT_DST}')


if __name__ == '__main__':
    main()
