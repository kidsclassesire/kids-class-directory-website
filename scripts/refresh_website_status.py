import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co'
SECRET_KEY = os.environ['SB_SECRET']
LOCAL_AUDIT_DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/website_link_audit.json'
TIMEOUT = 20
TRIES = 2
WORKERS = 10

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


def check_url(url):
    # Retries (TRIES) apply only to genuine transient network errors (timeout,
    # connection reset). A definitive HTTP response -- including 403/405 -- is never
    # retried with the same method: hitting a host repeatedly in quick succession is
    # exactly what trips Cloudflare-style bot protection, which then falsely flags an
    # otherwise-fine site as dead. On 403/405 we fall through to GET once, no more.
    last_status, last_err = None, None
    for method in ('HEAD', 'GET'):
        for attempt in range(TRIES):
            try:
                req = urllib.request.Request(url, headers=HEADERS, method=method)
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return True, resp.status, None
            except urllib.error.HTTPError as e:
                last_status, last_err = e.code, str(e)
                break  # definitive response -- don't retry this method again
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionResetError,
                    ConnectionRefusedError, OSError) as e:
                last_err = str(e)
                continue  # transient network issue -- worth one more try
            except Exception as e:
                # Catches malformed-URL cases (e.g. a scraped venue name used as a URL,
                # like "https://National%20Concert%20Hall") that aren't network errors.
                return False, None, str(e)
        if last_status is not None and last_status not in (403, 405):
            return last_status < 400, last_status, last_err
        # 403/405 (or no response at all) on this method -- fall through and try the next
    return False, last_status, last_err


def variants(url):
    p = urllib.parse.urlparse(url)
    host = p.netloc
    out = []

    def rebuild(new_scheme, new_host):
        return urllib.parse.urlunparse((new_scheme, new_host, p.path or '/', '', p.query, ''))

    if host.endswith('.com'):
        out.append(rebuild(p.scheme, host[:-4] + '.ie'))
    elif host.endswith('.ie'):
        out.append(rebuild(p.scheme, host[:-3] + '.com'))
    if host.startswith('www.'):
        out.append(rebuild(p.scheme, host[4:]))
    else:
        out.append(rebuild(p.scheme, 'www.' + host))
    other_scheme = 'http' if p.scheme == 'https' else 'https'
    out.append(rebuild(other_scheme, host))

    seen = set()
    result = []
    for v in out:
        if v != url and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def fetch_all_rows():
    headers = {'apikey': SECRET_KEY, 'Authorization': f'Bearer {SECRET_KEY}'}
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?select=id,website_url&order=id',
        headers={**headers, 'Range-Unit': 'items', 'Range': '0-1999'},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def patch_status(url, status, checked_at):
    headers = {
        'apikey': SECRET_KEY, 'Authorization': f'Bearer {SECRET_KEY}',
        'Content-Type': 'application/json', 'Prefer': 'return=minimal',
    }
    quoted = urllib.parse.quote(url, safe='')
    body = json.dumps({'website_status': status, 'website_checked_at': checked_at}).encode('utf-8')
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/classes?website_url=eq.{quoted}',
        data=body, headers=headers, method='PATCH',
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def main():
    rows = fetch_all_rows()
    urls = sorted(set(r['website_url'].strip() for r in rows if r.get('website_url')))
    print(f'Checking {len(urls)} unique URLs (timeout={TIMEOUT}s, {TRIES} tries per method)...')

    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(check_url, u): u for u in urls}
        done = 0
        for fut in as_completed(futures):
            u = futures[fut]
            ok, status, err = fut.result()
            results[u] = {'ok': ok, 'status': status, 'error': err}
            done += 1
            if done % 50 == 0:
                dead_so_far = sum(1 for v in results.values() if not v['ok'])
                print(f'[{done}/{len(urls)}] dead so far: {dead_so_far}')

    dead_urls = [u for u, r in results.items() if not r['ok']]
    print(f'\nCheck done. {len(dead_urls)} dead out of {len(urls)}.')

    print('Writing results back to classes.website_status / website_checked_at...')
    checked_at = datetime.now(timezone.utc).isoformat()
    written = 0
    for u in urls:
        status = 'ok' if results[u]['ok'] else 'dead'
        try:
            patch_status(u, status, checked_at)
            written += 1
        except Exception as e:
            print(f'  FAILED to write status for {u}: {e}')
    print(f'Wrote status for {written}/{len(urls)} URLs.')

    print('Looking for working alternates on dead ones (for local reference only)...')
    alt_found = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {}
        for u in dead_urls:
            for v in variants(u):
                futures[ex.submit(check_url, v)] = (u, v)
        for fut in as_completed(futures):
            orig, variant_url = futures[fut]
            ok, status, err = fut.result()
            if ok and orig not in alt_found:
                alt_found[orig] = variant_url

    out = {
        'checked_at': checked_at,
        'checked': len(urls),
        'dead': [
            {'url': u, 'error': results[u]['error'], 'status': results[u]['status'],
             'working_alternate': alt_found.get(u)}
            for u in dead_urls
        ],
    }
    json.dump(out, open(LOCAL_AUDIT_DST, 'w'), indent=2)
    print(f'\nDone. {len(dead_urls)} dead, {len(alt_found)} with a working alternate found.')
    print(f'Wrote {LOCAL_AUDIT_DST}')


if __name__ == '__main__':
    main()
