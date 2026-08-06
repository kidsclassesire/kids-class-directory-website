"""Resolve and store a Google Places `place_id` for each business in public.classes.

place_id is the one piece of Places API content Google's terms permit caching
indefinitely (everything else -- rating, review text, photos -- is meant to be
requested live, not warehoused: see
https://developers.google.com/maps/documentation/places/web-service/policies).
This script only ever writes google_place_id; it does not fetch or store rating,
review, or any other place content. Requires add_google_reviews_columns.sql to
have been run first (adds the google_place_id column).

One Places Text Search call per unique business (deduped by company_name+address,
since several class rows can share the same venue). A candidate is only written if
the returned name/address look like a confident match for what's stored (cheap
token-overlap check) -- known weak spot: businesses hosted inside a larger venue
(library, community centre) or multi-location franchises can match the venue's or
a sibling branch's listing instead of the actual business. Anything that fails the
check is skipped and logged rather than guessed, same spirit as the mismatch report
in scripts/google_geocode_missing.py.

Costs money (Places API Text Search). Always run --dry-run first.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) GOOGLE_API_KEY=... \
    python3 scripts/google_resolve_place_ids.py --dry-run
  SB_SECRET=... GOOGLE_API_KEY=... python3 scripts/google_resolve_place_ids.py --confirm --limit 25
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
CACHE_PATH = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_place_ids_cache.json'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_place_ids_audit.json'
LOW_CONFIDENCE_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_place_ids_low_confidence.txt'

# Rough, approximate USD estimate -- verify current Places API (New) Text Search
# pricing at https://mapsplatform.google.com/pricing/ before trusting this.
SEARCH_COST_PER_REQUEST = 0.035

PAGE_SIZE = 1000  # PostgREST caps a single response at this regardless of the Range requested

STOPWORDS = {'the', 'and', 'of', 'club', 'group', 'centre', 'center', 'ltd'}


def sb_headers(secret):
    return {'apikey': secret, 'Authorization': f'Bearer {secret}'}


def fetch_rows(secret):
    headers = sb_headers(secret)
    rows, offset = [], 0
    while True:
        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/classes?select=id,company_name,address,google_place_id&order=id',
            headers={**headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset + PAGE_SIZE - 1}'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.loads(resp.read())
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def patch_row(secret, row_id, place_id):
    headers = {**sb_headers(secret), 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}',
        data=json.dumps({'google_place_id': place_id}).encode(), headers=headers, method='PATCH',
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def text_search(query, api_key):
    url = 'https://places.googleapis.com/v1/places:searchText'
    body = json.dumps({'textQuery': query, 'regionCode': 'IE', 'languageCode': 'en'}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress',
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    places = data.get('places') or []
    return places[0] if places else None


def tokens(text):
    return {w for w in re.findall(r'[a-z0-9]+', (text or '').lower()) if w not in STOPWORDS and len(w) > 2}


def looks_like_match(company_name, address, candidate):
    name_tokens = tokens(company_name)
    candidate_name_tokens = tokens((candidate.get('displayName') or {}).get('text'))
    name_overlap = bool(name_tokens & candidate_name_tokens)

    addr_tokens = tokens(address)
    candidate_addr_tokens = tokens(candidate.get('formattedAddress'))
    addr_overlap = bool(addr_tokens & candidate_addr_tokens)

    return name_overlap and addr_overlap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Print planned calls/cost, make zero API calls')
    parser.add_argument('--limit', type=int, default=25, help='Cap number of unique businesses to look up')
    parser.add_argument('--confirm', action='store_true', help='Required to actually spend money / write to the DB')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    api_key = os.environ.get('GOOGLE_API_KEY')

    rows = fetch_rows(secret)
    rows = [r for r in rows if r.get('company_name') and r.get('address') and not r.get('google_place_id')]
    print(f'{len(rows)} rows with a company_name + address and no google_place_id yet.')

    by_key = {}
    for r in rows:
        key = (r['company_name'], r['address'])
        by_key.setdefault(key, []).append(r['id'])
    keys = list(by_key.keys())[:args.limit]
    print(f'{len(by_key)} unique businesses; looking up {len(keys)} (--limit {args.limit}).')
    print(f'Estimated cost: ${len(keys) * SEARCH_COST_PER_REQUEST:.2f} '
          f'({len(keys)} requests @ ~${SEARCH_COST_PER_REQUEST}/req -- verify current pricing before trusting this)')

    if args.dry_run:
        print('\n--dry-run: no API calls made, no DB writes.')
        return

    if not args.confirm:
        print('\nRefusing to run without --confirm (this spends money and writes to the live DB).')
        return

    if not api_key:
        raise SystemExit('GOOGLE_API_KEY is not set.')

    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

    audit = []
    low_confidence = []
    written = 0

    for i, key in enumerate(keys):
        company_name, address = key
        cache_key = f'{company_name}|||{address}'
        entry = cache.get(cache_key)

        if entry is None:
            query = f'{company_name}, {address}, Ireland'
            try:
                candidate = text_search(query, api_key)
            except urllib.error.HTTPError as e:
                print(f'[{i+1}/{len(keys)}] Text Search HTTP error for "{query}": {e}')
                candidate = None

            if not candidate:
                entry = {'matched': False}
            elif not looks_like_match(company_name, address, candidate):
                entry = {'matched': False, 'candidate': candidate, 'reason': 'low confidence'}
            else:
                entry = {'matched': True, 'candidate': candidate}

            cache[cache_key] = entry
            with open(CACHE_PATH, 'w') as f:
                json.dump(cache, f, indent=2)
            time.sleep(0.1)  # avoid hammering the API

        if not entry.get('matched'):
            print(f'[{i+1}/{len(keys)}] NO MATCH: {company_name} -- {address}')
            low_confidence.append({'company_name': company_name, 'address': address, **entry})
            continue

        place_id = entry['candidate'].get('id')
        row_ids = by_key[key]
        for row_id in row_ids:
            try:
                patch_row(secret, row_id, place_id)
                written += 1
            except Exception as e:
                print(f'[{i+1}/{len(keys)}] FAILED to write id={row_id}: {e}')
        print(f'[{i+1}/{len(keys)}] OK: {company_name} -- {place_id}, applied to {len(row_ids)} row(s)')
        audit.append({'company_name': company_name, 'address': address, 'row_ids': row_ids, 'google_place_id': place_id})

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    with open(LOW_CONFIDENCE_DST, 'w') as f:
        f.write('Businesses skipped -- no Places result, or the result didn\'t look like a confident match.\n')
        f.write('Not auto-applied -- review manually and re-run with a more specific address if needed.\n\n')
        for entry in low_confidence:
            f.write(f"{entry['company_name']} -- {entry['address']}\n")
            if entry.get('candidate'):
                cand = entry['candidate']
                f.write(f"  Google returned: {(cand.get('displayName') or {}).get('text')} -- {cand.get('formattedAddress')}\n")

    print(f'\nWrote google_place_id for {written} row(s) across {len(audit)} business(es).')
    print(f'{len(low_confidence)} business(es) skipped (no match / low confidence) -- see {LOW_CONFIDENCE_DST}')
    print(f'Audit log: {AUDIT_DST}')


if __name__ == '__main__':
    main()
