"""신뢰된 승인 제보로만 후보 비용을 비교한다. 운영 기본값·저장·공개 API 없음."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from agent.geometry import covered_length
from agent.data.facility_route import project


@dataclass(frozen=True)
class ReportEffectPolicy:
    radius_m: float
    weight: float


def _number(value, low, high):
    if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
        raise ValueError('유한한 숫자와 허용 범위를 확인하세요.')
    return value


def _time(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('시간대가 있는 승인·유효 시각이 필요합니다.') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('시간대가 필요합니다.')
    return result


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError('식별자·담당자·근거를 확인하세요.')
    return value


def compare_report_effects(result, reports, policy, *, as_of, graph):
    """서버가 신뢰한 검토 기록만 전달. 호출자의 인증을 대신하지 않는다.

    result는 TMAP compare 결과, 좌표는 [경도, 위도]. 원본을 수정하지 않는다.
    """
    if not isinstance(policy, ReportEffectPolicy):
        raise ValueError('명시한 반경·강도 설정이 필요합니다.')
    _number(policy.radius_m, 0.01, 200)
    _number(policy.weight, 0, 16)
    now = _time(as_of)
    if not isinstance(result, dict) or not isinstance(graph, dict):
        raise ValueError("경로 결과·좌표 기준 형식을 확인하세요.")
    for field in ("center", "scale"):
        pair = graph.get(field)
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("좌표 기준을 확인하세요.")
        for value in pair:
            _number(value, -1e8, 1e8)
    if any(value <= 0 for value in graph["scale"]):
        raise ValueError("좌표 축척은 양수여야 합니다.")
    if not isinstance(reports, list) or len(reports) > 1000:
        raise ValueError('검토 기록은 최대 1000건입니다.')
    active = []; seen = set()
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError('검토 기록 형식을 확인하세요.')
        rid = _text(report.get('id'))
        if rid in seen:
            raise ValueError('중복 제보 식별자입니다.')
        seen.add(rid)
        if report.get('status') != 'APPROVED' or report.get('resolved') is not False:
            continue
        if report.get('kind') not in ('light_failure', 'cctv_failure', 'walkway_obstruction'):
            continue
        _text(report.get('approved_by')); _text(report.get('evidence_ref'))
        approved = _time(report.get('approved_at'))
        start = _time(report.get('valid_from')); end = _time(report.get('valid_until'))
        if end <= start or end <= approved:
            raise ValueError('승인·유효기간을 확인하세요.')
        coords = report.get('coordinates')
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            raise ValueError('제보 좌표를 확인하세요.')
        _number(coords[0], 125, 128); _number(coords[1], 32, 34)
        if approved <= now and start <= now < end:
            x, y = project(graph, coords)
            active.append((rid, {'x': x, 'y': y}))
    output = deepcopy(result)
    routes = output.get('routes')
    if not isinstance(routes, list) or not 1 <= len(routes) <= 20:
        raise ValueError('경로 후보 1~20개가 필요합니다.')
    route_ids = set()
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("경로 후보 형식을 확인하세요.")
        rid = _text(route.get('id'))
        if rid in route_ids:
            raise ValueError('경로 식별자는 고유해야 합니다.')
        route_ids.add(rid)
        base = _number(route.get('comparison_cost'), 0, 1e12)
        _number(route.get('duration_minutes'), 0, 1e6)
        _number(route.get('distance_m'), 0, 1e8)
        if type(route.get('eligible_for_recommendation')) is not bool:
            raise ValueError('기존 우회 한도 적격 여부가 필요합니다.')
        coords = route.get('coordinates')
        if not isinstance(coords, list) or not 2 <= len(coords) <= 100000:
            raise ValueError('경로 좌표를 확인하세요.')
        points = []
        for point in coords:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError('경로 좌표를 확인하세요.')
            _number(point[0], 125, 128); _number(point[1], 32, 34)
            points.append(project(graph, point))
        affected, total = covered_length(points, [p for _, p in active], policy.radius_m)
        if total <= 0:
            raise ValueError('길이가 있는 경로가 필요합니다.')
        matched = sorted(rid for rid, p in active if covered_length(points, [p], policy.radius_m)[0] > 0)
        route['report_effect'] = {
            'base_cost': base, 'affected_length_m': round(affected, 4),
            'affected_percent': round(affected / total * 100, 4),
            'additional_cost': round(policy.weight * affected, 4),
            'adjusted_cost': round(base + policy.weight * affected, 4),
            'matched_report_ids': matched,
        }
    eligible = [r for r in routes if r['eligible_for_recommendation']]
    if not eligible:
        raise ValueError('기존 우회 한도 안의 경로가 필요합니다.')
    if output.get('preference') == 'fastest':
        key = lambda r: (r['duration_minutes'], r['distance_m'], r['id'])
    else:
        key = lambda r: (r['report_effect']['adjusted_cost'], r['distance_m'], r['id'])
    best = min(eligible, key=key)
    output['report_comparison'] = {
        'recommended_route_id': best['id'], 'baseline_recommended_route_id': result.get('recommended_route_id'),
        'radius_m': policy.radius_m, 'weight': policy.weight, 'as_of': as_of,
        'active_report_count': len(active), 'candidate_policy_only': True,
        'meaning': '승인된 제보 주변 구간의 비교 비용 후보. 안전 확률이 아닙니다.',
    }
    # 기본 추천 필드는 보존해 후보 계산을 운영 채택으로 오해하지 않게 한다.
    return output
