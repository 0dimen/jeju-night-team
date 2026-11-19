"""직접 선택한 기준의 같은 비중 비교. 기존 단일 preference 요청과 분리."""
from math import isfinite

ORDER = ('fastest', 'cctv', 'light')
LABELS = {'fastest': '이동 시간', 'cctv': 'CCTV 인접 구간', 'light': '조명 인접 구간'}


def normalize_criteria(criteria):
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 3:
        raise ValueError('비교 기준을 한 가지 이상 선택해 주세요.')
    if any(not isinstance(c, str) or c not in ORDER for c in criteria) or len(set(criteria)) != len(criteria):
        raise ValueError('중복되지 않은 지원 기준을 선택해 주세요.')
    return [c for c in ORDER if c in criteria]


def _number(value, minimum, maximum):
    if type(value) not in (int, float) or not isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('경로 시간·거리·시설 비율을 확인하세요.')
    return value


def rank_selected_criteria(result, criteria):
    criteria = normalize_criteria(criteria)
    routes = result['routes']
    eligible = [r for r in routes if r['eligible_for_recommendation']]
    if not eligible:
        raise ValueError('우회 한도 안의 경로가 필요합니다.')
    for row in routes:
        _number(row['duration_minutes'], .000001, 1e8)
        _number(row['distance_m'], .000001, 1e10)
        for key in ('cctv_percent', 'light_percent'):
            _number(row[key], 0, 100)
    fastest = min(row['duration_minutes'] for row in eligible)
    for row in routes:
        components = {'fastest': min(1, fastest / row['duration_minutes']),
                      'cctv': row['cctv_percent'] / 100, 'light': row['light_percent'] / 100}
        selected = {c: components[c] for c in criteria}
        row['criteria_components'] = selected
        # 순위 결정에는 반올림 전 값을 사용한다.
        row['criteria_score'] = sum(selected.values()) / len(criteria) * 100
    best = min(eligible, key=lambda r: (-r['criteria_score'], r['distance_m'], r['id']))
    result['recommended_route_id'] = best['id']
    result['selected_criteria'] = criteria
    result['parameters'].update(criteria_weights={c: 1 / len(criteria) for c in criteria},
        ranking_method='selected_criteria_equal_mean', legacy_comparison_cost_used_for_ranking=False)
    result['reason'] += ' 선택한 기준: ' + ' · '.join(LABELS[c] for c in criteria) + '.'
    result['reason'] += ' 선택한 기준만 같은 비중으로 비교했습니다. 이동 시간은 가장 빠른 적격 후보 대비 비율, 시설은 길이 중 인접 비율을 사용합니다. 이 점수는 안전 확률이 아닙니다.'
    return result
