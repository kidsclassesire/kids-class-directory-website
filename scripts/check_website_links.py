import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

SRC = '/tmp/all_websites.json'
DST = '/Users/davidmacmahon/kids-class-directory-website/downloads/website_link_audit.json'
TIMEOUT = 10
WORKERS = 20

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


def check_url(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS, method='HEAD')
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return True, resp.status, None
    except urllib.error.HTTPError as e:
        if e.code == 405 or e.code == 403:
            # some servers reject HEAD or bot-like requests; retry with GET
            try:
                req = urllib.request.Request(url, headers=HEADERS, method='GET')
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return True, resp.status, None
            except urllib.error.HTTPError as e2:
                return e2.code < 400, e2.code, str(e2)
            except Exception as e2:
                return False, None, str(e2)
        return e.code < 400, e.code, str(e)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionResetError,
            ConnectionRefusedError, OSError) as e:
        return False, None, str(e)
    except Exception as e:
        return False, None, str(e)


def variants(url):
    p = urllib.parse.urlparse(url)
    host = p.netloc
    out = []

    def rebuild(new_scheme, new_host):
        return urllib.parse.urlunparse((new_scheme, new_host, p.path or '/', '', p.query, ''))

    # TLD swap .com <-> .ie
    if host.endswith('.com'):
        out.append(rebuild(p.scheme, host[:-4] + '.ie'))
    elif host.endswith('.ie'):
        out.append(rebuild(p.scheme, host[:-3] + '.com'))

    # www toggle
    if host.startswith('www.'):
        out.append(rebuild(p.scheme, host[4:]))
    else:
        out.append(rebuild(p.scheme, 'www.' + host))

    # scheme toggle
    other_scheme = 'http' if p.scheme == 'https' else 'https'
    out.append(rebuild(other_scheme, host))

    # dedupe, drop the original
    seen = set()
    result = []
    for v in out:
        if v != url and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def main():
    rows = json.load(open(SRC))
    urls = sorted(set(r['website_url'].strip() for r in rows if r.get('website_url')))
    print(f'Checking {len(urls)} unique URLs...')

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
    print(f'\nFirst pass done. {len(dead_urls)} dead out of {len(urls)}.')
    print('Trying alternates for dead ones...')

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
        'checked': len(urls),
        'dead': [
            {'url': u, 'error': results[u]['error'], 'status': results[u]['status'],
             'working_alternate': alt_found.get(u)}
            for u in dead_urls
        ],
    }
    json.dump(out, open(DST, 'w'), indent=2)
    print(f'\nDone. {len(dead_urls)} dead, {len(alt_found)} with a working alternate found.')
    print(f'Wrote {DST}')


if __name__ == '__main__':
    main()
