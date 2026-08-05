"""Fill missing website_url, phone_number, facebook_url and instagram_url on public.classes.
Only ever fills null fields -- never overwrites an existing value.

Order per row:
  1. Places API (New) Text Search, if website_url or phone_number is null (paid).
  2. Scrape the (existing or newly-found) website's HTML for facebook.com/instagram.com
     links, if facebook_url or instagram_url is still null (free).
  3. Google Custom Search JSON API, only for whatever step 2 didn't find (paid).

Costs money (Places API + Custom Search API). Always run --dry-run first to see the request
count and estimated cost before spending anything. Requires add_social_link_columns.sql to
have been run first (facebook_url/instagram_url columns).

Run:
  SB_SECRET=... GOOGLE_API_KEY=... GOOGLE_CSE_CX=... python3 scripts/google_enrich_links.py --dry-run
  SB_SECRET=... GOOGLE_API_KEY=... GOOGLE_CSE_CX=... python3 scripts/google_enrich_links.py --confirm
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
CACHE_PATH = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_links_cache.json'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/google_links_audit.json'

# Rough, approximate USD estimates -- check current Google Cloud pricing before relying on these.
PLACES_COST_PER_REQUEST = 0.032   # Places API (New) Text Search, Pro tier (contact data fields)
CSE_COST_PER_REQUEST = 0.005      # Custom Search JSON API, after the first 100/day free

HEADERS_UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

SOCIAL_SKIP_PATTERNS = ('sharer', 'share.php', '/plugins/', 'intent/tweet', 'dialog/share')


PAGE_SIZE = 1000  # PostgREST caps a single response at this regardless of the Range requested


def sb_headers(secret):
    return {'apikey': secret, 'Authorization': f'Bearer {secret}'}


def fetch_incomplete_rows(secret):
    headers = sb_headers(secret)
    url = (
        f'{SUPABASE_URL}/rest/v1/classes'
        '?select=id,company_name,address,website_url,phone_number,facebook_url,instagram_url'
        '&or=(website_url.is.null,phone_number.is.null,facebook_url.is.null,instagram_url.is.null)'
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


def places_text_search(query, api_key):
    url = 'https://places.googleapis.com/v1/places:searchText'
    body = json.dumps({'textQuery': query}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.websiteUri,places.internationalPhoneNumber,places.displayName',
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    places = data.get('places') or []
    if not places:
        return None
    p = places[0]
    return {'website': p.get('websiteUri'), 'phone': p.get('internationalPhoneNumber')}


def scrape_social_links(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None, None

    def find(platform_host):
        pattern = rf'https?://(?:www\.)?{re.escape(platform_host)}/[^\s"\'<>]+'
        for m in re.findall(pattern, html):
            if not any(skip in m.lower() for skip in SOCIAL_SKIP_PATTERNS):
                return m.rstrip('/')
        return None

    return find('facebook.com'), find('instagram.com')


def custom_search(query, api_key, cx):
    url = 'https://www.googleapis.com/customsearch/v1?' + urllib.parse.urlencode({
        'key': api_key, 'cx': cx, 'q': query, 'num': 3,
    })
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read())
    return [item['link'] for item in data.get('items', [])]


def first_matching(urls, host):
    for u in urls:
        if host in u.lower() and not any(skip in u.lower() for skip in SOCIAL_SKIP_PATTERNS):
            return u
    return None


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
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--confirm', action='store_true')
    parser.add_argument('--skip-social', action='store_true',
                         help='Only fill website_url/phone_number via Places; skip the facebook/instagram '
                              'scrape step entirely (the free-scrape step proved unreliable -- see '
                              'scripts/cleanup_bad_social_links.py)')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    api_key = os.environ.get('GOOGLE_API_KEY')
    cse_cx = os.environ.get('GOOGLE_CSE_CX')

    rows = fetch_incomplete_rows(secret)
    if args.limit:
        rows = rows[:args.limit]
    print(f'{len(rows)} rows missing at least one of website/phone/facebook/instagram.')

    places_needed = sum(1 for r in rows if not r.get('website_url') or not r.get('phone_number'))
    print(f'Places API calls needed (website/phone missing): up to {places_needed}')
    print(f'Estimated Places cost: up to ${places_needed * PLACES_COST_PER_REQUEST:.2f}')
    print('(Social links: free scrape attempted first; Custom Search fallback cost depends on '
          'how many the scrape misses, so is not estimated up front.)')

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
    written = 0
    cse_calls = 0

    for i, row in enumerate(rows):
        rid = str(row['id'])
        entry = cache.get(rid, {})

        needs_website = not row.get('website_url')
        needs_phone = not row.get('phone_number')
        if (needs_website or needs_phone) and 'places' not in entry:
            query = f"{row['company_name']} {row.get('address') or ''}".strip()
            try:
                entry['places'] = places_text_search(query, api_key)
            except Exception as e:
                print(f'[{i+1}/{len(rows)}] Places error for "{query}": {e}')
                entry['places'] = None
            cache[rid] = entry
            with open(CACHE_PATH, 'w') as f:
                json.dump(cache, f, indent=2)
            time.sleep(0.1)

        website = row.get('website_url') or (entry.get('places') or {}).get('website')
        phone = row.get('phone_number') or (entry.get('places') or {}).get('phone')

        needs_facebook = not row.get('facebook_url')
        needs_instagram = not row.get('instagram_url')
        facebook = row.get('facebook_url')
        instagram = row.get('instagram_url')

        if not args.skip_social:
            if (needs_facebook or needs_instagram) and website and 'scraped_social' not in entry:
                fb, ig = scrape_social_links(website)
                entry['scraped_social'] = {'facebook': fb, 'instagram': ig}
                cache[rid] = entry
                with open(CACHE_PATH, 'w') as f:
                    json.dump(cache, f, indent=2)

            scraped = entry.get('scraped_social') or {}
            if needs_facebook and not facebook:
                facebook = scraped.get('facebook')
            if needs_instagram and not instagram:
                instagram = scraped.get('instagram')

            if (needs_facebook and not facebook or needs_instagram and not instagram) and cse_cx:
                if 'cse' not in entry:
                    query_base = f"{row['company_name']} {row.get('address') or ''}".strip()
                    cse_results = {}
                    try:
                        if needs_facebook and not facebook:
                            links = custom_search(f'{query_base} facebook', api_key, cse_cx)
                            cse_calls += 1
                            cse_results['facebook'] = first_matching(links, 'facebook.com')
                        if needs_instagram and not instagram:
                            links = custom_search(f'{query_base} instagram', api_key, cse_cx)
                            cse_calls += 1
                            cse_results['instagram'] = first_matching(links, 'instagram.com')
                    except Exception as e:
                        print(f'[{i+1}/{len(rows)}] Custom Search error for "{query_base}": {e}')
                    entry['cse'] = cse_results
                    cache[rid] = entry
                    with open(CACHE_PATH, 'w') as f:
                        json.dump(cache, f, indent=2)
                cse = entry.get('cse') or {}
                if needs_facebook and not facebook:
                    facebook = cse.get('facebook')
                if needs_instagram and not instagram:
                    instagram = cse.get('instagram')

        updates = {}
        if needs_website and website:
            updates['website_url'] = website
        if needs_phone and phone:
            updates['phone_number'] = phone
        if needs_facebook and facebook:
            updates['facebook_url'] = facebook
        if needs_instagram and instagram:
            updates['instagram_url'] = instagram

        if updates:
            try:
                patch_row(secret, row['id'], updates)
                written += 1
                audit.append({'id': row['id'], 'company_name': row['company_name'], 'updates': updates})
                print(f'[{i+1}/{len(rows)}] Updated id={row["id"]} ({row["company_name"]}): {updates}')
            except Exception as e:
                print(f'[{i+1}/{len(rows)}] FAILED to write id={row["id"]}: {e}')
        else:
            print(f'[{i+1}/{len(rows)}] Nothing found for id={row["id"]} ({row["company_name"]})')

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'\nWrote updates for {written}/{len(rows)} rows. {cse_calls} Custom Search calls made.')
    print(f'Audit log: {AUDIT_DST}')


if __name__ == '__main__':
    main()
