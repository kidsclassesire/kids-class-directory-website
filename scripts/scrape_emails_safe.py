"""Fill missing email_address on public.classes by scraping mailto: links off businesses'
existing website_url. No Google API involved (Places API doesn't expose email at all) -- free.

Same defensive pattern as scripts/scrape_social_links_safe.py, since the failure mode is the
same shape (a shared/generic address grabbed off a template footer, e.g. a web design agency's
own contact email in a "site by..." credit):
  1. Prefer mailto: links inside <footer>/<header> over a full-page match.
  2. A full-page fallback match is only accepted if the email's domain matches the business's
     own website domain (strong signal) or there's exactly one mailto: on the whole page.
  3. Pre-write cross-company de-dup filter: any address that would end up assigned to 2+
     companies is discarded unless every company sharing it resembles the address (same
     name_similarity-based brand check used for social links) -- catches a shared agency/
     webmaster inbox while still allowing one real franchise's shared inbox through.

Run:
  SB_SECRET=$(cat ~/Documents/kidspatch_secret.txt) python3 scripts/scrape_emails_safe.py --confirm
"""

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
CACHE_PATH = '/Users/davidmacmahon/kids-class-directory-website/downloads/email_scrape_cache.json'
AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/email_scrape_audit.json'
REJECTED_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/email_scrape_rejected.txt'
PAGE_SIZE = 1000

HEADERS_UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}
MAILTO_RE = re.compile(r'mailto:([^"\'\s?#>]+)', re.I)
FOOTER_HEADER_RE = re.compile(r'<(footer|header)\b[^>]*>(.*?)</\1>', re.I | re.S)
EMAIL_RE = re.compile(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$', re.I)
BAD_LOCAL_PARTS = ('noreply', 'no-reply', 'donotreply', 'webmaster', 'postmaster', 'abuse',
                    'example', 'yourname', 'sentry')
BAD_DOMAINS = ('sentry.io', 'wixpress.com', 'godaddy.com', 'cloudflare.com', 'example.com',
               'yourdomain.com', 'domain.com', 'schema.org', 'w3.org', 'godaddysites.com')
SHARED_HANDLE_THRESHOLD = 0.35


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


def fetch_known_website_domains(secret):
    rows = fetch_all(
        f'{SUPABASE_URL}/rest/v1/classes?select=website_url&website_url=not.is.null', sb_headers(secret),
    )
    domains = set()
    for r in rows:
        d = website_domain(r['website_url'])
        if d:
            domains.add(d)
    return domains


def fetch_target_rows(secret):
    url = (
        f'{SUPABASE_URL}/rest/v1/classes'
        '?select=id,company_name,website_url,email_address'
        '&email_address=is.null&website_url=not.is.null&order=id'
    )
    return fetch_all(url, sb_headers(secret))


def website_domain(website_url):
    host = urllib.parse.urlparse(website_url).netloc.lower()
    return host[4:] if host.startswith('www.') else host


def is_plausible_email(addr):
    if not EMAIL_RE.match(addr):
        return False
    local, domain = addr.lower().split('@', 1)
    if local in BAD_LOCAL_PARTS or domain in BAD_DOMAINS:
        return False
    if len(addr) > 100:
        return False
    return True


def normalize_words(s):
    return set(re.findall(r'[a-z0-9]+', s.lower()))


def name_similarity(company_name, email_or_domain):
    words = normalize_words(email_or_domain.replace('.', ' ').replace('-', ' ').replace('_', ' '))
    company_words = normalize_words(company_name)
    if not words or not company_words:
        overlap = 0.0
    else:
        overlap = len(words & company_words) / len(words | company_words)
    seq_ratio = SequenceMatcher(None, email_or_domain.lower(), company_name.lower()).ratio()
    return max(overlap, seq_ratio)


def same_brand_family(companies, email):
    return all(name_similarity(c, email) >= SHARED_HANDLE_THRESHOLD for c in companies)


def find_candidate(html, company_name, site_domain):
    footer_header_text = ''.join(m.group(2) for m in FOOTER_HEADER_RE.finditer(html))
    for m in MAILTO_RE.finditer(footer_header_text):
        addr = urllib.parse.unquote(m.group(1)).strip()
        if is_plausible_email(addr):
            return {'email': addr, 'source': 'footer_header'}

    all_matches = []
    for m in MAILTO_RE.finditer(html):
        addr = urllib.parse.unquote(m.group(1)).strip()
        if is_plausible_email(addr):
            all_matches.append(addr)
    if not all_matches:
        return None

    unique = sorted(set(a.lower() for a in all_matches))
    for addr in all_matches:
        domain = addr.lower().split('@', 1)[1]
        if domain == site_domain:
            return {'email': addr, 'source': 'fullpage_domainmatch'}
    if len(unique) == 1:
        return {'email': all_matches[0], 'source': 'fullpage_onlymatch'}
    return None


def scrape(website, company_name):
    try:
        req = urllib.request.Request(website, headers=HEADERS_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return {'error': str(e)}
    return {'candidate': find_candidate(html, company_name, website_domain(website))}


def patch_row(secret, row_id, email):
    headers = {**sb_headers(secret), 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?id=eq.{row_id}',
        data=json.dumps({'email_address': email}).encode(), headers=headers, method='PATCH',
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
    print(f'{len(rows)} rows have a website and are missing email_address.')

    known_domains = fetch_known_website_domains(secret)
    print(f'{len(known_domains)} distinct website domains already in the table (used as a trust signal).')

    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

    for i, row in enumerate(rows):
        rid = str(row['id'])
        if rid in cache:
            continue
        cache[rid] = scrape(row['website_url'], row['company_name'])
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        if (i + 1) % 50 == 0:
            print(f'[{i+1}/{len(rows)}] scraped')

    print('Scrape pass complete. Applying cross-company de-dup filter before any writes...')

    email_to_companies = defaultdict(set)
    for row in rows:
        entry = cache.get(str(row['id'])) or {}
        cand = entry.get('candidate')
        if cand:
            email_to_companies[cand['email'].lower()].add(row['company_name'])

    accepted, rejected = [], []
    for row in rows:
        entry = cache.get(str(row['id'])) or {}
        cand = entry.get('candidate')
        if not cand:
            continue
        companies = email_to_companies[cand['email'].lower()]
        email_domain = cand['email'].lower().split('@', 1)[1]
        trusted_domain = email_domain in known_domains
        if len(companies) >= 2 and not trusted_domain and not same_brand_family(companies, cand['email']):
            rejected.append({
                'id': row['id'], 'company_name': row['company_name'], 'email': cand['email'],
                'shared_with': sorted(companies - {row['company_name']})[:5],
            })
            continue
        accepted.append((row, cand['email']))

    print(f'{len(accepted)} rows to write, {len(rejected)} candidates rejected by the de-dup filter.')

    with open(REJECTED_DST, 'w') as f:
        f.write('Email candidates rejected because the same address matched 2+ distinct '
                'companies with no common brand resemblance (likely a shared agency/webmaster inbox).\n\n')
        for r in rejected:
            f.write(f"[{r['company_name']}] id={r['id']}: {r['email']}\n  also matched: {r['shared_with']}\n\n")
    print(f'Rejected-candidates report: {REJECTED_DST}')

    if not args.confirm:
        print('\nDry run (pass --confirm to write). Sample of what would be written:')
        for row, email in accepted[:10]:
            print(f'  id={row["id"]} ({row["company_name"]}): {email}')
        return

    audit = []
    written = 0
    for row, email in accepted:
        try:
            patch_row(secret, row['id'], email)
            written += 1
            audit.append({'id': row['id'], 'company_name': row['company_name'], 'email_address': email})
        except Exception as e:
            print(f'  FAILED id={row["id"]}: {e}')

    with open(AUDIT_DST, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f'Wrote {written}/{len(accepted)} rows. Audit: {AUDIT_DST}')


if __name__ == '__main__':
    main()
