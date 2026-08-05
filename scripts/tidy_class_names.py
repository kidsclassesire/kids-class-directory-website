"""Find near-duplicate class_types values within each company (whitespace/casing/punctuation
variants of what's really the same class name) and propose fixes. No Google API, no cost --
pure text analysis over what's already in the DB.

Two outputs, nothing is auto-applied to the DB:
  - downloads/tidy_class_names.sql   -- safe, mechanical fixes (whitespace/casing/punctuation
    only) using array_replace, ready to review and run in the Supabase SQL editor.
  - downloads/tidy_class_names_report.txt -- judgment calls (similar but not identical, e.g.
    differing age ranges in the label) for you to decide on manually.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/tidy_class_names.py
"""

import json
import os
import re
import urllib.request
from collections import Counter, defaultdict
from difflib import SequenceMatcher

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
SQL_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/tidy_class_names.sql'
REPORT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/tidy_class_names_report.txt'

SIMILARITY_THRESHOLD = 0.90
PAGE_SIZE = 1000  # PostgREST caps a single response at this regardless of the Range requested


def fetch_rows(secret):
    headers = {'apikey': secret, 'Authorization': f'Bearer {secret}'}
    url = f'{SUPABASE_URL}/rest/v1/classes?select=company_name,class_types&order=company_name'
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


def normalize(s):
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('’', "'").replace('‘', "'")
    return s


def sql_quote(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    secret = os.environ['SB_SECRET']
    rows = fetch_rows(secret)

    by_company = defaultdict(Counter)
    for row in rows:
        for ct in (row.get('class_types') or []):
            if ct:
                by_company[row['company_name']][normalize(ct)] += 1

    safe_fixes = []   # (company, old, new)
    judgment_calls = []  # (company, value_a, count_a, value_b, count_b, ratio)

    for company, counts in by_company.items():
        values = list(counts.keys())

        # Bucket by casing/punctuation-insensitive key -> mechanical, safe to auto-merge.
        buckets = defaultdict(list)
        for v in values:
            key = re.sub(r'[^a-z0-9]', '', v.lower())
            buckets[key].append(v)

        canonical_for = {}
        for key, variants in buckets.items():
            if len(variants) <= 1:
                canonical_for[variants[0]] = variants[0]
                continue
            canonical = max(variants, key=lambda v: (counts[v], v))
            for v in variants:
                canonical_for[v] = canonical
                if v != canonical:
                    safe_fixes.append((company, v, canonical))

        # Among the remaining distinct canonical forms, flag close-but-not-identical pairs.
        canon_values = sorted(set(canonical_for.values()))
        for i in range(len(canon_values)):
            for j in range(i + 1, len(canon_values)):
                a, b = canon_values[i], canon_values[j]
                ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    judgment_calls.append((company, a, counts[a], b, counts[b], ratio))

    print(f'{len(by_company)} companies, {sum(len(c) for c in by_company.values())} distinct class_types values.')
    print(f'{len(safe_fixes)} safe mechanical fixes (whitespace/casing/punctuation only).')
    print(f'{len(judgment_calls)} judgment calls needing manual review.')

    with open(SQL_DST, 'w') as f:
        f.write('-- Mechanical class_types fixes (whitespace/casing/punctuation variants of the\n')
        f.write('-- same class name) found by scripts/tidy_class_names.py. Review before running.\n\n')
        for company, old, new in safe_fixes:
            f.write(
                f'update public.classes set class_types = array_replace(class_types, {sql_quote(old)}, {sql_quote(new)}) '
                f'where company_name = {sql_quote(company)} and {sql_quote(old)} = any(class_types);\n'
            )
    print(f'Wrote {SQL_DST}')

    with open(REPORT_DST, 'w') as f:
        f.write('Class name variants that are similar but not identical -- likely the same class\n')
        f.write('with a different age range or wording, so not auto-merged. Review manually.\n\n')
        for company, a, ca, b, cb, ratio in sorted(judgment_calls, key=lambda t: -t[5]):
            f.write(f'[{company}] ({ratio:.2f} similar)\n')
            f.write(f'  "{a}"  ({ca} row(s))\n')
            f.write(f'  "{b}"  ({cb} row(s))\n\n')
    print(f'Wrote {REPORT_DST}')


if __name__ == '__main__':
    main()
