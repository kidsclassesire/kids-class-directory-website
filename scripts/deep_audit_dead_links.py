import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

AUDIT_SRC = '/Users/davidmacmahon/kids-class-directory-website/downloads/website_link_audit.json'
CLASSES_SRC = '/tmp/classes_min.json'
DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/website_link_audit_deep.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


def fetch_text(url, timeout=15, verify_ssl=True):
    ctx = None
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=HEADERS, method='GET')
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read(200000)
        try:
            return raw.decode('utf-8', errors='ignore')
        except Exception:
            return raw.decode('latin-1', errors='ignore')


def retry_check(url, timeout=25, tries=2):
    last_err = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method='GET')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, resp.status, None
        except Exception as e:
            last_err = str(e)
    return False, None, last_err


def norm_phone(p):
    return re.sub(r'\D', '', p or '')


def check_wayback(domain):
    try:
        url = f'https://archive.org/wayback/available?url={urllib.parse.quote(domain)}'
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        snap = data.get('archived_snapshots', {}).get('closest')
        if not snap:
            return {'has_snapshot': False, 'timestamp': None, 'snapshot_url': None}
        return {'has_snapshot': True, 'timestamp': snap.get('timestamp'), 'snapshot_url': snap.get('url')}
    except Exception as e:
        return {'has_snapshot': None, 'error': str(e)}


def main():
    audit = json.load(open(AUDIT_SRC))
    classes = json.load(open(CLASSES_SRC))

    url_to_rows = {}
    for r in classes:
        u = (r.get('website_url') or '').strip()
        if u:
            url_to_rows.setdefault(u, []).append(r)

    def confidence(d):
        err = (d['error'] or '')
        status = d['status']
        if 'nodename nor servname' in err or 'Name or service not known' in err:
            return 'HIGH'
        if status == 410:
            return 'HIGH'
        if status == 404:
            return 'HIGH'
        if 'certificate' in err.lower():
            return 'SSL'
        if status in (500, 503):
            return 'MEDIUM'
        if status in (400, 403) and 'facebook.com' in d['url']:
            return 'FACEBOOK'
        if status in (400, 403):
            return 'LOW'
        if 'timed out' in err:
            return 'TIMEOUT'
        return 'UNKNOWN'

    def is_tld_swap(d):
        if not d['working_alternate']:
            return False
        o = urllib.parse.urlparse(d['url']).netloc.lower().lstrip('www.')
        a = urllib.parse.urlparse(d['working_alternate']).netloc.lower().lstrip('www.')
        return o != a

    tld_swap = [d for d in audit['dead'] if is_tld_swap(d)]
    timeouts = [d for d in audit['dead'] if confidence(d) == 'TIMEOUT']
    high_conf = [d for d in audit['dead'] if confidence(d) == 'HIGH']
    ssl_issues = [d for d in audit['dead'] if confidence(d) == 'SSL']

    print(f'TLD-swap candidates: {len(tld_swap)}')
    print(f'Timeout retries: {len(timeouts)}')
    print(f'High-confidence dead (wayback check): {len(high_conf)}')
    print(f'SSL-broken (content refetch): {len(ssl_issues)}')

    results = {'tld_swap': [], 'timeout_retry': [], 'wayback': [], 'ssl_refetch': []}

    # 1. TLD-swap content matching
    print('\n--- TLD-swap content matching ---')
    for d in tld_swap:
        rows = url_to_rows.get(d['url'], [])
        names = list({r['company_name'] for r in rows})
        phones = {norm_phone(r.get('phone_number')) for r in rows if r.get('phone_number')}
        addr = next((r.get('address') for r in rows if r.get('address')), '')
        county_match = None
        m = re.search(r'(?:co\.?\s*)?([A-Z][a-z]+)(?:,|\s+Ireland)', addr or '')
        try:
            text = fetch_text(d['working_alternate'], timeout=15)
            text_l = text.lower()
        except Exception as e:
            text_l = ''
            print(f'  fetch failed for {d["working_alternate"]}: {e}')

        name_hit = any(n.split()[0].lower() in text_l for n in names if n)
        phone_hit = any(norm_phone(p) and norm_phone(p) in re.sub(r'\D', '', text_l) for p in phones)
        ireland_hit = 'ireland' in text_l or ('.ie' in d['working_alternate'])
        verdict = 'LIKELY SAME BUSINESS' if (name_hit or phone_hit) else (
            'UNCLEAR - no Irish/company signal found' if not ireland_hit else 'POSSIBLY SAME - has Ireland signal but no name/phone match')
        entry = {
            'company': '; '.join(names), 'dead_url': d['url'], 'alternate': d['working_alternate'],
            'name_matched_in_page': name_hit, 'phone_matched_in_page': phone_hit,
            'verdict': verdict,
        }
        results['tld_swap'].append(entry)
        print(f'  {names}: {verdict}')

    # 2. Timeout retries
    print('\n--- Timeout retries (25s, 2 tries) ---')
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(retry_check, d['url']): d for d in timeouts}
        for fut in as_completed(futs):
            d = futs[fut]
            ok, status, err = fut.result()
            results['timeout_retry'].append({'url': d['url'], 'now_ok': ok, 'status': status, 'error': err})
    n_recovered = sum(1 for r in results['timeout_retry'] if r['now_ok'])
    print(f'  {n_recovered}/{len(timeouts)} came back OK on retry')

    # 3. Wayback machine checks for high-confidence dead
    print('\n--- Wayback Machine checks ---')
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(check_wayback, d['url']): d for d in high_conf}
        for fut in as_completed(futs):
            d = futs[fut]
            wb = check_wayback_result = fut.result()
            rows = url_to_rows.get(d['url'], [])
            names = list({r['company_name'] for r in rows})
            results['wayback'].append({'company': '; '.join(names), 'url': d['url'], **wb})

    # 4. SSL-broken refetch with verification off
    print('\n--- SSL-broken content refetch (verification off) ---')
    for d in ssl_issues:
        rows = url_to_rows.get(d['url'], [])
        names = list({r['company_name'] for r in rows})
        try:
            text = fetch_text(d['url'], timeout=15, verify_ssl=False)
            snippet = re.sub(r'\s+', ' ', text)[:300]
            still_real = len(text.strip()) > 200 and 'domain' not in text.lower()[:2000] or True
            results['ssl_refetch'].append({'company': '; '.join(names), 'url': d['url'],
                                            'fetched_ok': True, 'snippet': snippet})
        except Exception as e:
            results['ssl_refetch'].append({'company': '; '.join(names), 'url': d['url'],
                                            'fetched_ok': False, 'error': str(e)})

    json.dump(results, open(DST, 'w'), indent=2)
    print(f'\nWrote {DST}')


if __name__ == '__main__':
    main()
