import json, time, urllib.request, urllib.parse, re

PLAN_PATH = '/Users/davidmacmahon/kids-class-directory-website/scripts/split_locations/plan.json'
OUT_PATH = '/Users/davidmacmahon/kids-class-directory-website/scripts/split_locations/geocoded.json'

plan = json.load(open(PLAN_PATH))

# Ireland (incl. Northern Ireland) bounding box, same as project convention
LAT_MIN, LAT_MAX = 51.3, 55.5
LON_MIN, LON_MAX = -10.8, -5.3

UA = 'KidsPatchDirectory/1.0 (davidmacmahon1@gmail.com)'

def nominatim_query(q):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({
        'q': q, 'format': 'json', 'limit': 1, 'countrycodes': 'ie',
    })
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read())
    except Exception as e:
        return None, f'error: {e}'
    if not results:
        return None, 'no results'
    lat, lon = float(results[0]['lat']), float(results[0]['lon'])
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None, f'out of bounds: {lat},{lon}'
    return (lat, lon), 'ok'

def drop_leading_venue(addr):
    parts = [p.strip() for p in addr.split(',')]
    if len(parts) > 2:
        return ', '.join(parts[1:])
    return None

def area_only(addr):
    parts = [p.strip() for p in addr.split(',')]
    # drop eircode-like tokens and 'Ireland'
    parts = [p for p in parts if p.lower() != 'ireland' and not re.match(r'^[A-Z]\d{2}\s?[A-Z0-9]{4}$', p)]
    if len(parts) >= 2:
        return ', '.join(parts[-2:])
    return None

results = {}
total = sum(len(v) for v in plan.values())
done = 0
for rid, addrs in plan.items():
    results[rid] = []
    for addr in addrs:
        coords, status = nominatim_query(addr)
        time.sleep(1.1)
        attempt = 'full'
        if coords is None:
            fallback = drop_leading_venue(addr)
            if fallback:
                coords, status = nominatim_query(fallback)
                time.sleep(1.1)
                attempt = 'dropped-venue'
        if coords is None:
            fallback = area_only(addr)
            if fallback:
                coords, status = nominatim_query(fallback)
                time.sleep(1.1)
                attempt = 'area-only'
        done += 1
        entry = {'address': addr, 'lat': coords[0] if coords else None, 'lon': coords[1] if coords else None,
                  'status': status, 'attempt': attempt if coords else 'failed'}
        results[rid].append(entry)
        print(f'[{done}/{total}] id={rid} "{addr[:60]}" -> {entry["lat"]},{entry["lon"]} ({entry["status"]}, {entry["attempt"]})')
        json.dump(results, open(OUT_PATH, 'w'), indent=2)

failed = [(rid, e['address']) for rid, es in results.items() for e in es if e['lat'] is None]
print(f'\nDone. {len(failed)} addresses failed to geocode:')
for rid, addr in failed:
    print(' ', rid, addr)
