"""두 시연 구간에서 '최단 경로'와 '가로등·공공 CCTV 인접 구간을 선호하는 경로'를 직접 계산한다.

연구용이다. 결과는 data/open/facility_routes/에 쓴다.
앞 단계: scripts/fix_light_axes.py → scripts/collect_foot_routes.py (출발·도착점을 여기서 가져온다)
실행: 저장소 루트에서
  .venv/bin/python scripts/build_facility_routes.py                  # 저장소에 든 도로망으로 오프라인 계산
  .venv/bin/python scripts/build_facility_routes.py --download-osm   # data/open/osm/ 파일이 없을 때만 새로 받음
선택: --light-radius 15 --cctv-radius 50 --light-weight 1 --cctv-weight 1 --max-detour 1.5 --cctv-source datahub|standard
"""
import argparse
import csv
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'open'
OSM_DIR = RAW / 'osm'
OUT = RAW / 'facility_routes'
TEMP = ROOT / 'data' / 'raw' / 'tmp'  # Git 제외 임시 파일
sys.path.insert(0, str(ROOT))
from agent.data.cctv import select  # noqa: E402
from agent.data.facility_route import build_graph, nearest_node, plan_routes, score_edges  # noqa: E402
from agent.data.routes import load_routes  # noqa: E402

OVERPASS = 'https://overpass-api.de/api/interpreter'
UA = 'jeju-night-team-research/0.1 (one-off public-area walk network study)'
MARGIN_DEG = 0.006  # 출발·도착 상자 바깥으로 약 600m
POLICY = ROOT / 'config' / 'cctv_selection.yaml'
SEGMENTS = {
    'yeondong': {'lights': ['derived/jeju_city_streetlights_20241010_axisfixed.csv', 'jeju_city_streetlights_20241010.csv']},
    'seogwipo': {'lights': ['seogwipo_streetlights_20250725.csv']},
}
# 행정안전부 전국 CCTV 표준데이터의 열 이름을 기존 전처리 코드의 열 이름으로 맞춘다.
STANDARD_COLUMNS = {'설치목적구분': '설치목적', 'WGS84위도': '위도', 'WGS84경도': '경도', '데이터기준일자': '데이터기준일',
                    '소재지도로명주소': '도로명주소', '소재지지번주소': '지번주소'}


def decode(path):
    data = path.read_bytes()
    return data.decode('utf-8-sig' if data[:3] == b'\xef\xbb\xbf' else 'cp949')


def load_lights(names):
    path = next((RAW / n for n in names if (RAW / n).exists()), None)
    if path is None:
        raise SystemExit(f'가로등 원본 없음: {names}')
    points = []
    for row in csv.DictReader(io.StringIO(decode(path))):
        if (row.get('등종류') or row.get('종류') or '').strip() not in ('가로등', '보안등'):
            continue
        try:
            lat, lon = float(row['위도']), float(row['경도'])
        except (TypeError, ValueError):
            continue
        if 33 <= lat <= 34.1 and 126 <= lon <= 127:
            points.append((lon, lat))
    return path.name, points


def load_cctv(source):
    if source == 'datahub':
        path = RAW / 'jeju_cctv_20221215.csv'
    else:
        original = RAW / 'jeju_cctv_mois_standard.csv'
        rows = list(csv.DictReader(io.StringIO(decode(original))))
        TEMP.mkdir(parents=True, exist_ok=True)
        path = TEMP / 'cctv_standard_renamed.csv'
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=[STANDARD_COLUMNS.get(c, c) for c in rows[0]])
        writer.writeheader()
        writer.writerows({STANDARD_COLUMNS.get(k, k): v for k, v in row.items()} for row in rows)
        path.write_bytes(buffer.getvalue().encode('utf-8-sig'))
    selected = select(path, POLICY)
    return {'file': path.name if source == 'datahub' else original.name + ' (열 이름만 변환)', 'source_rows': selected['source_rows'], 'selected_rows': len(selected['rows']),
            'include_purposes': selected['include_purposes'], 'policy_version': selected['policy_version'],
            'basis_dates': sorted({r['basis_date'] for r in selected['rows']})}, [(r['lng'], r['lat']) for r in selected['rows']]


def download_osm(key, endpoints):
    lons, lats = [p[0] for p in endpoints], [p[1] for p in endpoints]
    box = (min(lats) - MARGIN_DEG, min(lons) - MARGIN_DEG, max(lats) + MARGIN_DEG, max(lons) + MARGIN_DEG)
    query = f'[out:json][timeout:60];way["highway"]({box[0]:.5f},{box[1]:.5f},{box[2]:.5f},{box[3]:.5f});(._;>;);out body;'
    request = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({'data': query}).encode(),
                                     headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read().decode('utf-8'))
    body['_collection'] = {'query': query, 'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                           'osm_base': body.get('osm3s', {}).get('timestamp_osm_base')}
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    (OSM_DIR / f'{key}_overpass.json').write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')


def feature(route_id, label, summary):
    return {'type': 'Feature', 'properties': {
        'id': route_id, 'label': label, 'duration_minutes': summary['duration_minutes'],
        'duration_basis': '경로 길이를 보행 4.5km/h로 나눈 계산값, 현장 실측 아님',
        'length_m': summary['length_m'], 'light_fraction': summary['light_fraction'],
        'cctv_fraction': summary['cctv_fraction'], 'walkability_checked': True,
        'walkability_check_basis': 'OSM highway 태그 중 OSRM 보행 프로필과 같은 종류만 사용. 지도상 정보만 확인',
        'onsite_checked': False}, 'geometry': {'type': 'LineString', 'coordinates': summary['coordinates']}}


def run(key, collected, args, cctv_info, cctv_points):
    osm_path = OSM_DIR / f'{key}_overpass.json'
    start, goal = (tuple(p) for p in collected['snapped_endpoints'])
    if args.download_osm and not osm_path.exists():
        download_osm(key, [start, goal])
    if not osm_path.exists():
        raise SystemExit(f'{osm_path.name} 없음: --download-osm 으로 먼저 받으세요.')
    osm = json.loads(osm_path.read_text(encoding='utf-8'))
    graph = build_graph(osm['elements'], start)
    light_file, lights = load_lights(SEGMENTS[key]['lights'])
    score_edges(graph, lights, args.light_radius, 'light')
    score_edges(graph, cctv_points, args.cctv_radius, 'cctv')
    a, a_gap = nearest_node(graph, start)
    b, b_gap = nearest_node(graph, goal)
    plan = plan_routes(graph, a, b, args.light_weight, args.cctv_weight, args.max_detour)
    observed = osm['_collection']['fetched_at']
    summary = {'segment': collected['segment'], 'same_route': plan['same_route'], 'weights_used': plan['weights_used'],
               'parameters': {'light_radius_m': args.light_radius, 'cctv_radius_m': args.cctv_radius,
                              'light_weight': args.light_weight, 'cctv_weight': args.cctv_weight,
                              'max_detour': args.max_detour},
               'endpoint_snap_m': [round(a_gap, 1), round(b_gap, 1)],
               'graph': {'nodes': len(graph['nodes']), 'edges': len(graph['edges']), 'osm_base': osm['_collection'].get('osm_base')},
               'light_file': light_file, 'cctv': cctv_info,
               'routes': {name: {k: plan[name][k] for k in ('length_m', 'duration_minutes', 'light_fraction', 'cctv_fraction')}
                          for name in ('shortest', 'facility_preferred')},
               'osrm_reference': collected['routes'], 'meaning': plan['meaning']}
    collection = {'type': 'FeatureCollection', 'properties': {
        'synthetic': False, 'source_name': 'OpenStreetMap contributors 도로망으로 직접 계산한 보행 경로',
        'source_url': 'https://www.openstreetmap.org/copyright', 'observed_at': observed,
        'license_note': '© OpenStreetMap contributors, ODbL1.0. 공개 서비스 채택 전 출처 표시·이용 조건 확인',
        'attribution_url': 'https://www.openstreetmap.org/copyright', 'fix_map_url': 'https://www.openstreetmap.org/fixthemap',
        'rights_confirmed': False, 'coordinate_system_confirmed': True,
        'coordinate_evidence': 'OSM 노드의 WGS84 경도·위도. RFC7946',
        'operationally_adopted': False, 'onsite_checked': False, 'calculation': summary},
        'features': [feature('SHORTEST', '최단 경로', plan['shortest']),
                     feature('FACILITY', '시설 선호 경로', plan['facility_preferred'])]}
    path = OUT / f'{key}_facility_routes_{args.cctv_source}.geojson'
    path.write_text(json.dumps(collection, ensure_ascii=False, indent=1), encoding='utf-8')
    load_routes(path)  # 기존 경로 파일 검사(출처·좌표·같은 끝점)를 통과하는지 확인
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download-osm', action='store_true')
    parser.add_argument('--light-radius', type=float, default=15)
    parser.add_argument('--cctv-radius', type=float, default=50)
    parser.add_argument('--light-weight', type=float, default=1.0)
    parser.add_argument('--cctv-weight', type=float, default=1.0)
    parser.add_argument('--max-detour', type=float, default=1.5)
    parser.add_argument('--cctv-source', choices=('datahub', 'standard'), default='datahub')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    collected = json.loads((RAW / 'foot_routes' / 'collection_summary.json').read_text(encoding='utf-8'))
    cctv_info, cctv_points = load_cctv(args.cctv_source)
    summaries = [run(key, item, args, cctv_info, cctv_points) for key, item in zip(SEGMENTS, collected)]
    (OUT / f'summary_{args.cctv_source}.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summaries, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
