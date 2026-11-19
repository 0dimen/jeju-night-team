"""공개 지점 두 구간의 보행 경로를 FOSSGIS OSRM routed-foot에서 받아 data/open/foot_routes/에 보관한다.

연구용 일회 수집 스크립트다. 앱 기능이 아니며 개인 위치를 넣지 않는다. 공개 지점의 결과만 저장소에 넣는다.
- 요청은 초당 1회 이하, 모든 응답을 data/raw/osrm_cache/(Git 제외)에 저장하고 재실행 시 재사용한다(재실행해도 재요청하지 않음).
- 기본 경로 + (서비스 대안이 없으면) 공개 가로등 위치 한 곳을 경유한 조사 대안.
  경유 대안은 임의 우회로이며 시설이 많은 길을 찾은 것이 아니다. 그 용도는 build_facility_routes.py.
원본 CSV는 data/open/에 들어 있다. 출처는 data/open/README.md.
실행: 저장소 루트에서  .venv/bin/python scripts/collect_foot_routes.py
"""
import csv
import hashlib
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'open'
OUT = RAW / 'foot_routes'
sys.path.insert(0, str(ROOT))
from agent.data.foot_route_import import prepare_foot_candidates  # noqa: E402

CACHE = ROOT / 'data' / 'raw' / 'osrm_cache'
UA = 'jeju-night-team-research/0.1 (one-off public-point route study)'
OSRM = 'https://routing.openstreetmap.de/routed-foot/route/v1/foot/'
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
_last = [0.0]
_fetched_at = []

SEGMENTS = [
    {'key': 'yeondong', 'label': '삼무공원~누웨마루거리',
     'lights': ('jeju_city_streetlights_20241010.csv', '위도', '경도'),
     'start': ['삼무공원'], 'end': ['누웨마루거리 공중화장실', '누웨마루거리', '누웨마루'],
     'viewbox': '126.45,33.51,126.52,33.46'},
    {'key': 'seogwipo', 'label': '서귀포 중앙로62번길~매일올레시장',
     'lights': ('seogwipo_streetlights_20250725.csv', '위도', '경도'),
     'start': ['중앙로62번길'], 'end': ['서귀포매일올레시장', '서귀포 매일올레시장', '매일올레시장'],
     'viewbox': '126.54,33.27,126.59,33.23'},
]


def fetch(url):
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + '.json')
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        _fetched_at.append(saved['fetched_at'])  # 캐시를 다시 쓸 때도 실제로 받은 시각을 기록한다
        return saved['body']
    wait = 1.2 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode('utf-8'))
    _last[0] = time.time()
    _fetched_at.append(datetime.now(timezone.utc).isoformat(timespec='seconds'))
    path.write_text(json.dumps({'url': url, 'fetched_at': _fetched_at[-1],
                                'body': body}, ensure_ascii=False), encoding='utf-8')
    return body


def geocode(queries, viewbox):
    for query in queries:
        params = urllib.parse.urlencode({'q': query, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'kr',
                                         'viewbox': viewbox, 'bounded': 1, 'accept-language': 'ko'})
        found = fetch(f'{NOMINATIM}?{params}')
        if found:
            hit = found[0]
            return {'query': query, 'lat': float(hit['lat']), 'lon': float(hit['lon']),
                    'display_name': hit.get('display_name'), 'category': hit.get('category'),
                    'type': hit.get('type'), 'osm': f"{hit.get('osm_type')}/{hit.get('osm_id')}"}
    raise SystemExit(f'지점 검색 실패: {queries}')


def route(points, alternatives=False):
    coords = ';'.join(f'{lon:.6f},{lat:.6f}' for lon, lat in points)
    alt = 'true' if alternatives else 'false'
    return fetch(f'{OSRM}{coords}?overview=full&geometries=geojson&steps=true&alternatives={alt}')


def meters(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2)) * 111320
    return math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * 110540)


def distance_to_line(p, line):
    best = float('inf')
    kx = math.cos(math.radians(p[1])) * 111320
    px, py = p[0] * kx, p[1] * 110540
    for a, b in zip(line, line[1:]):
        ax, ay, bx, by = a[0] * kx, a[1] * 110540, b[0] * kx, b[1] * 110540
        dx, dy = bx - ax, by - ay
        t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def load_lights(name, lat_col, lon_col):
    data = (RAW / name).read_bytes()
    encoding = 'utf-8-sig' if data[:3] == b'\xef\xbb\xbf' else 'cp949'  # 제주시는 UTF-8(BOM), 서귀포는 CP949
    out = []
    for row in csv.DictReader(data.decode(encoding).splitlines()):
        try:
            lat, lon = float(row[lat_col]), float(row[lon_col])
        except (TypeError, ValueError):
            continue
        if 33.0 <= lat <= 34.1 and 126.0 <= lon <= 127.0:  # 축이 뒤바뀐 행은 여기서 고치지 않고 제외
            out.append((lon, lat))
    return out


def has_backtrack(points):
    seen = set()
    previous = None
    for point in points:
        key = (round(point[0], 6), round(point[1], 6))
        if key != previous and key in seen:
            return True
        seen.add(key)
        previous = key
    return False


def collect(segment):
    start = geocode(segment['start'], segment['viewbox'])
    end = geocode(segment['end'], segment['viewbox'])
    a, b = (start['lon'], start['lat']), (end['lon'], end['lat'])
    base = route([a, b], alternatives=True)
    base_fetched_at = _fetched_at[-1]
    if base.get('code') != 'Ok':
        raise SystemExit(f"{segment['key']} 기본 경로 실패: {base.get('code')}")
    base_route = base['routes'][0]
    base_line = base_route['geometry']['coordinates']
    responses = [base]
    alternative = {'kind': 'provider_alternative'} if len(base['routes']) > 1 else None
    if alternative is None:
        direct = meters(a, b)
        candidates = []
        for light in load_lights(*segment['lights']):
            offset = distance_to_line(light, base_line)
            detour = meters(a, light) + meters(light, b)
            if 40 <= offset <= 150 and detour <= direct * 1.8:
                candidates.append((detour, offset, light))
        candidates.sort()
        for detour, offset, light in candidates[:12]:
            via = route([a, light, b])
            if via.get('code') != 'Ok':
                continue
            via_route = via['routes'][0]
            line = via_route['geometry']['coordinates']
            if line == base_line or has_backtrack(line):
                continue
            if via_route['distance'] > base_route['distance'] * 1.7:
                continue
            responses.append(via)
            alternative = {'kind': 'via_public_streetlight', 'via_lon': light[0], 'via_lat': light[1],
                           'via_offset_from_base_m': round(offset, 1),
                           'via_source_file': segment['lights'][0],
                           'note': '조사용 임의 우회로. 서비스가 제안한 동등 대안이나 시설이 많은 길·안전 추천이 아님'}
            break
    if alternative is None:
        raise SystemExit(f"{segment['key']} 대안 경로를 찾지 못함")
    observed_at = base_fetched_at[:19] + '+00:00'
    candidates_file = prepare_foot_candidates(responses, observed_at)
    meta = {'segment': segment['label'], 'collected_at': observed_at, 'start': start, 'end': end,
            'snap_distance_m': [round(w.get('distance', 0), 1) for w in base['waypoints']],
            'snapped_endpoints': [w['location'] for w in base['waypoints']], 'alternative': alternative,
            'routes': [{'id': f['properties']['id'], 'distance_m': round(f['properties']['provider_distance_m'], 1),
                        'duration_min': round(f['properties']['duration_minutes'], 2),
                        'points': len(f['geometry']['coordinates'])} for f in candidates_file['features']],
            'caveats': '지도상 보행 프로필 경로. 현장·현재 통행·점등 상태 미확인. rights_confirmed=false'}
    candidates_file['properties']['collection'] = meta
    key = segment['key']
    (OUT / f'{key}_osrm_responses.json').write_text(json.dumps(responses, ensure_ascii=False), encoding='utf-8')
    (OUT / f'{key}_route_candidates.geojson').write_text(
        json.dumps(candidates_file, ensure_ascii=False, indent=1), encoding='utf-8')
    return meta


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    summary = [collect(segment) for segment in SEGMENTS]
    (OUT / 'collection_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))
