"""Splits multi-location `classes` rows (address field concatenating several
real venues, or a vague area-list) into one row per location, using the plan
built by build_plan.py and coordinates from geocode_plan.py. Also deletes a
handful of pure-duplicate "Various Locations" stub rows that add no unique
info once their sibling business is already represented by detailed rows.

Run: SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/split_locations/write_split.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(os.path.join(HERE, 'plan.json')))
geocoded = json.load(open(os.path.join(HERE, 'geocoded.json')))

DELETE_DUPLICATE_STUB_IDS = [464, 465, 511, 529, 561]

EIRCODE_RE = re.compile(r'\b([A-Z]\d{2}\s?[A-Z0-9]{4})\b')


def fetch_all_rows():
    headers = {'apikey': SECRET_KEY, 'Authorization': f'Bearer {SECRET_KEY}'}
    rows, offset, page = [], 0, 1000
    while True:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/classes?select=*&order=id',
            headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + page - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def patch_row(row_id, fields):
    url = f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}'
    body = json.dumps(fields).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='PATCH')
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def insert_row(fields):
    url = f'{SUPABASE_URL}/rest/v1/classes'
    body = json.dumps(fields).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def delete_row(row_id):
    url = f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}'
    req = urllib.request.Request(url, headers=HEADERS, method='DELETE')
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def extract_eircode(addr):
    m = EIRCODE_RE.search(addr)
    return m.group(1) if m else None


def main():
    print('Fetching current live rows...')
    rows_by_id = {r['id']: r for r in fetch_all_rows()}
    print(f'Fetched {len(rows_by_id)} rows.')

    split_ids = sorted(int(k) for k in plan.keys())
    total_inserts = 0
    total_patches = 0
    skipped_no_original = []

    for rid in split_ids:
        original = rows_by_id.get(rid)
        if not original:
            skipped_no_original.append(rid)
            continue
        addrs = plan[str(rid)]
        geo = geocoded[str(rid)]
        assert len(addrs) == len(geo)

        # First address updates the existing row in place (preserves id/FKs).
        first_addr, first_geo = addrs[0], geo[0]
        patch_fields = {
            'address': first_addr,
            'latitude': first_geo['lat'],
            'longitude': first_geo['lon'],
            'eircode': extract_eircode(first_addr),
        }
        patch_row(rid, patch_fields)
        total_patches += 1
        print(f'PATCH id={rid}: "{first_addr[:70]}" -> {first_geo["lat"]},{first_geo["lon"]}')

        # Remaining addresses become new rows, copying every other field.
        for addr, g in zip(addrs[1:], geo[1:]):
            new_row = {k: v for k, v in original.items() if k != 'id'}
            new_row['address'] = addr
            new_row['latitude'] = g['lat']
            new_row['longitude'] = g['lon']
            new_row['eircode'] = extract_eircode(addr)
            insert_row(new_row)
            total_inserts += 1
            print(f'  INSERT (from {rid}): "{addr[:70]}" -> {g["lat"]},{g["lon"]}')

    print(f'\nSplit complete: {total_patches} rows updated in place, {total_inserts} new rows inserted.')
    if skipped_no_original:
        print(f'WARNING: {len(skipped_no_original)} plan ids not found live (already deleted/changed?): {skipped_no_original}')

    print(f'\nDeleting {len(DELETE_DUPLICATE_STUB_IDS)} pure-duplicate stub rows...')
    for did in DELETE_DUPLICATE_STUB_IDS:
        if did in rows_by_id:
            delete_row(did)
            print(f'  DELETE id={did} ({rows_by_id[did]["company_name"]})')
        else:
            print(f'  SKIP id={did}: not found live')

    print('\nDone.')


if __name__ == '__main__':
    main()
