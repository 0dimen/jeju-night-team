"""SYNTHETIC 미터 평면. 원의 합집합과 선분의 교차 길이를 계산한다."""
from math import sqrt, hypot, isfinite
from numbers import Real
from agent.common import check_schema, stable_hash, load_yaml

FACILITIES = [dict(id='CCTV-A1', type='cctv', x=150., y=0.),
              dict(id='CCTV-A2', type='cctv', x=400., y=20.),
              dict(id='CCTV-B1', type='cctv', x=150., y=200.),
              dict(id='CCTV-B2', type='cctv', x=350., y=200.),
              dict(id='CCTV-B3', type='cctv', x=550., y=210.),
              dict(id='CCTV-B4', type='cctv', x=750., y=200.),
              dict(id='CCTV-B5', type='cctv', x=930., y=200.)]
ROUTES = [dict(id='A', points=[(0., 0.), (950., 0.)], minutes=12),
          dict(id='B', points=[(0., 200.), (1100., 200.)], minutes=14)]


def covered_length(points, facilities, radius):
    if isinstance(radius,bool) or not isinstance(radius,Real) or not isfinite(radius) or radius <= 0:
        raise ValueError('반경은 양수여야 합니다.')
    covered = total = 0.
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        length = hypot(x2-x1, y2-y1)
        if length == 0:
            continue
        total += length
        ux, uy = (x2-x1)/length, (y2-y1)/length
        intervals = []
        for f in facilities:
            dx, dy = f['x']-x1, f['y']-y1
            along = dx*ux + dy*uy
            perpendicular2 = max(0., dx*dx + dy*dy - along*along)
            if perpendicular2 > radius*radius:
                continue
            delta = sqrt(max(0., radius*radius-perpendicular2))
            left, right = max(0., along-delta), min(length, along+delta)
            if right > left:
                intervals.append((left, right))
        end = -1.
        for left, right in sorted(intervals):
            covered += max(0., right-max(left, end))
            end = max(end, right)
    return covered, total


def analyze(request, radius=50, events=(), facilities=None, routes=None):
    check_schema('route_request', request)
    base = FACILITIES if facilities is None else facilities
    routes = ROUTES if routes is None else routes
    events=list(events)
    inventory={f['id']:f for f in base}
    states = {}
    for e in events:
        check_schema('facility_change', e)
        if e['facility_id'] not in inventory:
            raise ValueError('자료에 없는 시설의 상태를 바꿀 수 없습니다.')
        if e['type'] != inventory[e['facility_id']]['type']:
            raise ValueError('시설 유형이 일치하지 않습니다.')
        if e['before'] != states.get(e['facility_id'],'normal'):
            raise ValueError('시설의 이전 상태가 일치하지 않습니다.')
        states[e['facility_id']] = e['after']
    active = [f for f in base if states.get(f['id'], 'normal') not in ('not_working', 'damaged')]
    source_version = 'SYNTHETIC-' + stable_hash({'facilities': base, 'events': list(events)})
    logic = f'SYNTHETIC-union-v1-radius-{radius}'
    outputs = []
    for route in routes:
        near, total = covered_length(route['points'], [f for f in active if f['type'] == 'cctv'], radius)
        if total<=0:
            raise ValueError('길이가 없는 경로는 비율을 계산할 수 없습니다.')
        outputs.append(dict(id=route['id'], rank=1, distance=f'{total:g}m', duration=f"{route['minutes']}分".replace('分', '분'),
                            indicators={'cctv': {'status': 'confirmed' if states else 'verified',
                                                  'value': round(near/total, 6) if total else 0.,
                                                  'display': f'경로의 {near/total*100 if total else 0.:.1f}%가 CCTV {radius:g}m 이내'},
                                        'streetlight': {'status': 'unavailable'},
                                        'activity': {'status': 'historical', 'display': 'SYNTHETIC 2025년 8월 월별 지역 방문 통계'}}))
    # 월별 활동량은 정렬에 넣지 않는다. 가상 우회 허용 정책은 두지 않는다.
    use_cctv = 'cctv' in request['preferences']
    ranked = sorted(outputs, key=lambda r: (-r['indicators']['cctv']['value'] if use_cctv else 0, float(r['duration'][:-1]), r['id']))
    for index, route in enumerate(ranked, 1):
        route['rank'] = index
    detour = '대안 경로 없음'
    if len(outputs) >= 2:
        a, b = outputs[:2]
        distance = float(b['distance'][:-1])-float(a['distance'][:-1])
        minutes = float(b['duration'][:-1])-float(a['duration'][:-1])
        detour = f"{b['id']}가 {a['id']}보다 {distance:g}m, {minutes:g}분 더 김"
    result = dict(run_id='SYNTHETIC-' + stable_hash([request, source_version, logic, routes]),
                  data_version=source_version, logic_version=logic, routes=ranked,
                  comparison={'detour': detour, 'rank_reason': 'CCTV 인접 구간 비율 다음 이동 시간 순' if use_cctv else '이동 시간 순; 과거 월별 활동 통계는 정렬에서 제외'},
                  unavailable_preferences=[p for p in request['preferences'] if p == 'streetlight'],
                  limitations=['SYNTHETIC 합성 예시이며 실제 길찾기 결과가 아닙니다.'] + [v['limitation'] for v in load_yaml('registry/indicators.yaml').values()],
                  sources=[{'name': 'SYNTHETIC 시설 위치·월별 통계', 'observed_at': '2025-08'}])
    return check_schema('analysis_result', result)
