"""One-off fix for phone_number values corrupted upstream into a stringified
float (e.g. "353863317289.0" instead of "353863317289") -- found while
spot-checking generated business pages on 2026-07-31/08-01. Trims the
trailing ".0" via individual PATCH requests using the secret key (writes to
`classes` require the secret key -- the public/anon key is read-only per RLS).

Run: SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/fix_phone_numbers.py
"""

import json
import os
import re
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
SECRET_KEY = os.environ['SB_SECRET']

HEADERS = {
    'apikey': SECRET_KEY,
    'Authorization': f'Bearer {SECRET_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal',
}


def fetch_corrupted_rows():
    # PostgREST regex match operator (match. / ~) for a POSIX regex on a text column.
    url = f'{SUPABASE_URL}/rest/v1/classes?select=id,phone_number&phone_number=match.%5E%5Cd%2B%5C.0%24'
    req = urllib.request.Request(url, headers={'apikey': SECRET_KEY, 'Authorization': f'Bearer {SECRET_KEY}'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def patch_phone(row_id, new_value):
    url = f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}'
    body = json.dumps({'phone_number': new_value}).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='PATCH')
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main():
    rows = fetch_corrupted_rows()
    print(f'Found {len(rows)} rows with a corrupted phone_number.')
    fixed = 0
    for row in rows:
        old = row['phone_number']
        if not re.fullmatch(r'\d+\.0', old or ''):
            continue
        new = old[:-2]
        patch_phone(row['id'], new)
        fixed += 1
        print(f'  id={row["id"]}: "{old}" -> "{new}"')
    print(f'Fixed {fixed} rows.')


if __name__ == '__main__':
    main()
