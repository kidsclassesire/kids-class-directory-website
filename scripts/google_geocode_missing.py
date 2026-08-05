"""Geocode public.classes rows using the Google Geocoding API.

Default mode: only rows with a null latitude/longitude get geocoded, and the result is
written straight to the DB (pure null-fill, safe to automate) -- same fields as the free
Nominatim pass in geocode_new_candidates.py, for rows that one never resolved.

--full mode: geocodes EVERY row with a non-null address, including ones that already have
coordinates. Existing coordinates are never overwritten automatically -- if Google's result
is more than ~300m from what's stored, it's written to a mismatch report for manual review
instead. eircode is filled only when it was null.

Costs money (Google Geocoding API, ~$5 / 1000 requests as of 2026). Always run --dry-run
first to see the row/request count and estimated cost before spending anything.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) GOOGLE_API_KEY=... \
    python3 scripts/google_geocode_missing.py --dry-run [--full]
  SB_SECRET=... GOOGLE_API_KEY=... python3 scripts/google_geocode_missing.py --confirm [--full]
"""

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
CACHE_PATH = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_geocode_cache.json'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_geocode_audit.json'
MISMATCH_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_geocode_mismatches.txt'

# Same sanity box admin.html's Data Quality review uses (IE_BOUNDS) -- reject anything outside it.
IE_BOUNDS = (51.0, 55.5, -10.5, -5.0)
COST_PER_REQUEST = 0.005  # USD, Geocoding API pay-as-you-go rate
MISMATCH_THRESHOLD_M = 300  # flag existing coords more than this far from Google's result
PAGE_SIZE = 1000  # PostgREST caps a single response at this regardless of the Range requested


def sb_headers(secret):
    return {'apikey': secret, 'Authorization': f'Bearer {secret}'}


def fetch_all(url, headers):
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


def fetch_rows(secret, full):
    if full:
        url = f'{SUPABASE_URL}/rest/v1/classes?select=id,company_name,address,eircode,latitude,longitude&order=id'
    else:
        url = (
            f'{SUPABASE_URL}/rest/v1/classes'
            '?select=id,company_name,address,eircode,latitude,longitude'
            '&or=(latitude.is.null,longitude.is.null)'
            '&coords_flag_dismissed=eq.false&order=id'
        )
    return fetch_all(url, sb_headers(secret))


def geocode(address, api_key):
    url = 'https://maps.googleapis.com/maps/api/geocode/json?' + urllib.parse.urlencode({
        'address': address, 'region': 'ie', 'key': api_key,
    })
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read())
    if data.get('status') != 'OK' or not data.get('results'):
        return None
    result = data['results'][0]
    loc = result['geometry']['location']
    postcode = next(
        (c['long_name'] for c in result.get('address_components', [])
         if 'postal_code' in c.get('types', [])),
        None,
    )
    return {
        'latitude': loc['lat'], 'longitude': loc['lng'],
        'formatted_address': result.get('formatted_address'), 'postcode': postcode,
    }


def in_bounds(lat, lon):
    lat_min, lat_max, lon_min, lon_max = IE_BOUNDS
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


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
    parser.add_argument('--dry-run', action='store_true', help='Print planned calls/cost, make zero API calls')
    parser.add_argument('--full', action='store_true', help='Re-check every row, not just ones missing coordinates')
    parser.add_argument('--limit', type=int, default=None, help='Cap number of unique addresses to geocode')
    parser.add_argument('--confirm', action='store_true', help='Required to actually spend money / write to the DB')
    parser.add_argument('--apply-mismatches-over', type=float, default=None,
                         help='In --full mode, auto-apply Google\'s coordinates for existing rows whose '
                              'mismatch distance (meters) is at or above this value, instead of only reporting it')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    api_key = os.environ.get('GOOGLE_API_KEY')

    rows = fetch_rows(secret, args.full)
    rows = [r for r in rows if r.get('address')]
    mode = 'FULL AUDIT (all rows)' if args.full else 'missing-coordinates only'
    print(f'Mode: {mode}')
    print(f'{len(rows)} rows with a non-null address.')

    addresses = sorted(set(r['address'] for r in rows))
    if args.limit:
        addresses = addresses[:args.limit]
    print(f'{len(addresses)} unique addresses to geocode.')

    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

    todo = [a for a in addresses if a not in cache]
    print(f'{len(cache)} already cached, {len(todo)} new requests needed.')
    print(f'Estimated cost: ${len(todo) * COST_PER_REQUEST:.2f} ({len(todo)} requests @ ${COST_PER_REQUEST}/req)')

    if args.dry_run:
        print('\n--dry-run: no API calls made, no DB writes.')
        return

    if not args.confirm:
        print('\nRefusing to run without --confirm (this spends money and writes to the live DB).')
        return

    if not api_key:
        raise SystemExit('GOOGLE_API_KEY is not set.')

    for i, addr in enumerate(todo):
        try:
            result = geocode(addr, api_key)
        except urllib.error.HTTPError as e:
            print(f'[{i+1}/{len(todo)}] HTTP error for "{addr}": {e}')
            result = None
        if result and not in_bounds(result['latitude'], result['longitude']):
            print(f'[{i+1}/{len(todo)}] REJECTED (outside Ireland bounds): {addr} -> {result}')
            result = None
        cache[addr] = result
        status = 'OK' if result else 'NOT FOUND'
        print(f'[{i+1}/{len(todo)}] {status}: {addr}')
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        time.sleep(0.1)  # Google's quota is generous, but avoid hammering it

    print('\nApplying results (filling nulls only; existing coordinates are never overwritten)...')
    audit = []
    mismatches = []
    written = 0
    for row in rows:
        result = cache.get(row['address'])
        if not result:
            continue

        has_coords = row.get('latitude') is not None and row.get('longitude') is not None
        if not has_coords:
            updates = {'latitude': result['latitude'], 'longitude': result['longitude']}
            if not row.get('eircode') and result.get('postcode'):
                updates['eircode'] = result['postcode']
            try:
                patch_row(secret, row['id'], updates)
                written += 1
                audit.append({
                    'id': row['id'], 'company_name': row['company_name'], 'address': row['address'],
                    'updates': updates, 'google_formatted_address': result.get('formatted_address'),
                })
            except Exception as e:
                print(f'  FAILED to write id={row["id"]}: {e}')
        elif args.full:
            dist = haversine_m(row['latitude'], row['longitude'], result['latitude'], result['longitude'])
            if dist > MISMATCH_THRESHOLD_M:
                entry = {
                    'id': row['id'], 'company_name': row['company_name'], 'address': row['address'],
                    'stored': (row['latitude'], row['longitude']),
                    'google': (result['latitude'], result['longitude']),
                    'distance_m': round(dist), 'google_formatted_address': result.get('formatted_address'),
                }
                if args.apply_mismatches_over is not None and dist >= args.apply_mismatches_over:
                    try:
                        patch_row(secret, row['id'], {'latitude': result['latitude'], 'longitude': result['longitude']})
                        entry['applied'] = True
                        audit.append({
                            'id': row['id'], 'company_name': row['company_name'], 'address': row['address'],
                            'updates': {'latitude': result['latitude'], 'longitude': result['longitude']},
                            'google_formatted_address': result.get('formatted_address'),
                            'note': f'corrected large mismatch, was {round(dist)}m off',
                        })
                        written += 1
                    except Exception as e:
                        print(f'  FAILED to apply mismatch fix id={row["id"]}: {e}')
                        entry['applied'] = False
                else:
                    mismatches.append(entry)

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'Wrote {written} new-coordinate rows. Audit log: {AUDIT_DST}')

    if args.full:
        with open(MISMATCH_DST, 'w') as f:
            f.write(f'Rows where stored coordinates differ from Google by more than {MISMATCH_THRESHOLD_M}m.\n')
            f.write('Not auto-applied -- review and fix manually (existing coordinates are never overwritten automatically).\n\n')
            for m in sorted(mismatches, key=lambda x: -x['distance_m']):
                f.write(f"[{m['company_name']}] id={m['id']} -- {m['distance_m']}m off\n")
                f.write(f"  address: {m['address']}\n")
                f.write(f"  stored:  {m['stored']}\n")
                f.write(f"  google:  {m['google']}  ({m['google_formatted_address']})\n\n")
        print(f'{len(mismatches)} existing-coordinate mismatches found. Report: {MISMATCH_DST}')


if __name__ == '__main__':
    main()
