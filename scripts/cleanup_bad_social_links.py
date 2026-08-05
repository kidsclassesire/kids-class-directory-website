"""One-off cleanup for scripts/google_enrich_links.py's free-scrape step, which turned out to
grab shared widget/tracking links off business websites instead of each business's own social
page (e.g. 215 unrelated "Parent & Toddler Group" listings all got assigned the same
instagram.com/tots.spots handle). Nulls out facebook_url/instagram_url values that are either:
  - shared across 2+ distinct company_name values (a real business never shares a social
    profile with an unrelated business), or
  - match a known-garbage pattern (tracking pixels, xmlns namespace refs, legal/privacy pages).

website_url and phone_number (sourced from Places API, not scraping) were checked and are NOT
affected -- this only touches facebook_url/instagram_url.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/cleanup_bad_social_links.py --confirm
"""

import argparse
import json
import os
import urllib.request
from collections import defaultdict

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/cleanup_bad_social_links_audit.json'
PAGE_SIZE = 1000

BAD_PATTERNS = ('/tr?', 'fbml', '/about/', '/legal/', '/policies/', '/policy/', '/privacy',
                '/tos', 'sharer', 'share.php', '/plugins/', 'developers.facebook', 'facebook.com/help')


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
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    rows = fetch_all(
        f'{SUPABASE_URL}/rest/v1/classes?select=id,company_name,facebook_url,instagram_url'
        '&or=(facebook_url.not.is.null,instagram_url.not.is.null)&order=id',
        sb_headers(secret),
    )
    print(f'{len(rows)} rows have a facebook_url or instagram_url set.')

    fb_companies = defaultdict(set)
    ig_companies = defaultdict(set)
    for row in rows:
        if row.get('facebook_url'):
            fb_companies[row['facebook_url']].add(row['company_name'])
        if row.get('instagram_url'):
            ig_companies[row['instagram_url']].add(row['company_name'])

    def is_bad(url, companies_for_url):
        if not url:
            return False
        if any(p in url.lower() for p in BAD_PATTERNS):
            return True
        return len(companies_for_url[url]) >= 2

    to_clear = []
    for row in rows:
        updates = {}
        if row.get('facebook_url') and is_bad(row['facebook_url'], fb_companies):
            updates['facebook_url'] = None
        if row.get('instagram_url') and is_bad(row['instagram_url'], ig_companies):
            updates['instagram_url'] = None
        if updates:
            to_clear.append((row, updates))

    print(f'{len(to_clear)} rows have a bad facebook_url/instagram_url to clear.')

    if not args.confirm:
        print('Dry run (pass --confirm to apply). Sample:')
        for row, updates in to_clear[:10]:
            print(f'  id={row["id"]} ({row["company_name"]}): clearing {list(updates.keys())}')
        return

    audit = []
    cleared = 0
    for row, updates in to_clear:
        try:
            patch_row(secret, row['id'], updates)
            cleared += 1
            audit.append({
                'id': row['id'], 'company_name': row['company_name'],
                'cleared_facebook_url': row.get('facebook_url') if 'facebook_url' in updates else None,
                'cleared_instagram_url': row.get('instagram_url') if 'instagram_url' in updates else None,
            })
        except Exception as e:
            print(f'  FAILED id={row["id"]}: {e}')

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'Cleared {cleared}/{len(to_clear)} rows. Audit log: {AUDIT_DST}')


if __name__ == '__main__':
    main()
