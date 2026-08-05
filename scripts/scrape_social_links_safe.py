"""Hardened replacement for the social-link scrape step in google_enrich_links.py, which
turned out to grab shared widget/tracking links instead of each business's own Facebook/
Instagram page (see downloads/cleanup_bad_social_links_audit.json -- 755/1400 rows written
were garbage). No Google API involved, no cost.

Fixes vs the old approach, in order of how much they matter:
  1. Pre-write filter, not post-hoc cleanup: candidates are collected for EVERY row first,
     then any URL that would end up assigned to 2+ distinct companies is discarded for all
     of them before a single DB write happens. This is the same signal that caught the
     original contamination (a real business never shares a social profile with an unrelated
     business) -- previously applied as a cleanup pass, now applied before writing at all.
  2. Prefer links inside <footer>/<header> (where real "follow us" links actually live) over
     a full-page regex match, which is what grabbed random unrelated links before.
  3. If a candidate is only found via a full-page fallback (no footer/header hit), it's only
     accepted when the URL's handle textually resembles the company name -- this alone would
     have rejected the original "tots.spots" / "thefamilyedit" contamination, since those
     handles share no words with the ~200 unrelated business names they got attached to.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/scrape_social_links_safe.py --confirm
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
CACHE_PATH = '/Users/davidmacmahon/kids-class-directory-website/downloads/social_scrape_v2_cache.json'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/social_scrape_v2_audit.json'
REJECTED_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/social_scrape_v2_rejected.txt'
PAGE_SIZE = 1000

HEADERS_UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}
BAD_PATTERNS = ('/tr?', 'fbml', '/about/', '/legal/', '/policies/', '/policy/', '/privacy',
                '/tos', 'sharer', 'share.php', '/plugins/', 'developers.facebook', 'facebook.com/help',
                '/search', '?q=', 'query=', '/events/', '/hashtag/', '/photo', '/watch/')
# Note: '/groups/' is deliberately NOT excluded -- a Facebook Group is a legitimate business/
# community presence, not a widget artifact (learned the hard way after over-filtering these).
LINK_RE = {
    'facebook': re.compile(r'https?://(?:www\.)?facebook\.com/[^\s"\'<>]+', re.I),
    'instagram': re.compile(r'https?://(?:www\.)?instagram\.com/[^\s"\'<>]+', re.I),
}
FOOTER_HEADER_RE = re.compile(r'<(footer|header)\b[^>]*>(.*?)</\1>', re.I | re.S)
NAME_SIMILARITY_THRESHOLD = 0.4

# When a URL is shared by 2+ companies, don't just blacklist generic words (tried that --
# "massage" slipped through as a false brand match between unrelated baby-massage
# practitioners sharing a widget link, since it's not an obviously generic word). Instead,
# require that EVERY company sharing the URL individually resembles the handle text via the
# same name_similarity() used for the full-page fallback match, just at a lower bar -- this
# is what actually separates "Bloom Baby Classes (Dublin South)" / "...North West Ireland"
# both plausibly being bloombabyclasses (0.60-0.65) from unrelated businesses sharing a
# widget link (0.13-0.34 in spot checks, comfortably below legitimate brand matches).
SHARED_HANDLE_THRESHOLD = 0.35


def same_brand_family(companies, url):
    return all(name_similarity(c, url) >= SHARED_HANDLE_THRESHOLD for c in companies)


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


def fetch_target_rows(secret):
    url = (
        f'{SUPABASE_URL}/rest/v1/classes'
        '?select=id,company_name,website_url,facebook_url,instagram_url'
        '&website_url=not.is.null&or=(facebook_url.is.null,instagram_url.is.null)&order=id'
    )
    return fetch_all(url, sb_headers(secret))


def clean_url(u):
    return u.rstrip(').,;\'"').rstrip('/')


def is_bad(url):
    return any(p in url.lower() for p in BAD_PATTERNS)


def normalize_words(s):
    return set(re.findall(r'[a-z0-9]+', s.lower()))


def name_similarity(company_name, url):
    path = re.sub(r'^https?://(?:www\.)?(?:facebook|instagram)\.com/', '', url, flags=re.I)
    handle = re.split(r'[/?#]', path)[0]
    handle_words = normalize_words(handle.replace('.', ' ').replace('-', ' ').replace('_', ' '))
    company_words = normalize_words(company_name)
    if not handle_words or not company_words:
        return 0.0
    overlap = len(handle_words & company_words) / len(handle_words | company_words)
    seq_ratio = SequenceMatcher(None, handle.lower(), company_name.lower()).ratio()
    return max(overlap, seq_ratio)


def find_candidate(html, company_name, platform):
    regex = LINK_RE[platform]

    footer_header_text = ''.join(m.group(2) for m in FOOTER_HEADER_RE.finditer(html))
    for m in regex.finditer(footer_header_text):
        url = clean_url(m.group(0))
        if not is_bad(url):
            return {'url': url, 'source': 'footer_header'}

    for m in regex.finditer(html):
        url = clean_url(m.group(0))
        if is_bad(url):
            continue
        if name_similarity(company_name, url) >= NAME_SIMILARITY_THRESHOLD:
            return {'url': url, 'source': 'fullpage_namematch'}

    return None


def scrape(website, company_name):
    try:
        req = urllib.request.Request(website, headers=HEADERS_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return {'error': str(e)}
    return {
        'facebook': find_candidate(html, company_name, 'facebook'),
        'instagram': find_candidate(html, company_name, 'instagram'),
    }


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
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    secret = os.environ['SB_SECRET']
    rows = fetch_target_rows(secret)
    if args.limit:
        rows = rows[:args.limit]
    print(f'{len(rows)} rows have a website and are missing facebook_url and/or instagram_url.')

    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

    for i, row in enumerate(rows):
        rid = str(row['id'])
        if rid in cache:
            continue
        result = scrape(row['website_url'], row['company_name'])
        cache[rid] = result
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        if (i + 1) % 50 == 0:
            print(f'[{i+1}/{len(rows)}] scraped')

    print('Scrape pass complete. Applying cross-company de-dup filter before any writes...')

    url_to_companies = {'facebook': defaultdict(set), 'instagram': defaultdict(set)}
    for row in rows:
        entry = cache.get(str(row['id'])) or {}
        for platform in ('facebook', 'instagram'):
            cand = entry.get(platform)
            if cand:
                url_to_companies[platform][cand['url']].add(row['company_name'])

    accepted, rejected = [], []
    for row in rows:
        entry = cache.get(str(row['id'])) or {}
        updates = {}
        for platform, field in (('facebook', 'facebook_url'), ('instagram', 'instagram_url')):
            if row.get(field):
                continue
            cand = entry.get(platform)
            if not cand:
                continue
            companies = url_to_companies[platform][cand['url']]
            if len(companies) >= 2 and not same_brand_family(companies, cand['url']):
                rejected.append({
                    'id': row['id'], 'company_name': row['company_name'], 'platform': platform,
                    'url': cand['url'], 'reason': f'shared by {len(companies)} distinct companies '
                                                    'with no common brand word',
                    'shared_with': sorted(companies - {row['company_name']})[:5],
                })
                continue
            updates[field] = cand['url']
        if updates:
            accepted.append((row, updates))

    print(f'{len(accepted)} rows to write, {len(rejected)} candidates rejected by the de-dup filter.')

    with open(REJECTED_DST, 'w') as f:
        f.write('Candidates found by scraping but rejected because the same URL matched 2+ '
                'distinct companies (almost certainly a shared widget, not a real profile).\n\n')
        for r in rejected:
            f.write(f"[{r['company_name']}] id={r['id']} {r['platform']}: {r['url']}\n")
            f.write(f"  also matched: {r['shared_with']}\n\n")
    print(f'Rejected-candidates report: {REJECTED_DST}')

    if not args.confirm:
        print('\nDry run (pass --confirm to write). Sample of what would be written:')
        for row, updates in accepted[:10]:
            print(f'  id={row["id"]} ({row["company_name"]}): {updates}')
        return

    audit = []
    written = 0
    for row, updates in accepted:
        try:
            patch_row(secret, row['id'], updates)
            written += 1
            audit.append({'id': row['id'], 'company_name': row['company_name'], 'updates': updates})
        except Exception as e:
            print(f'  FAILED id={row["id"]}: {e}')

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'Wrote {written}/{len(accepted)} rows. Audit: {AUDIT_DST}')


if __name__ == '__main__':
    main()
