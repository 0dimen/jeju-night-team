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
    tied = [r for r in eligible if r['criteria_score'] == best['criteria_score']]
    if len(routes) == 1:
        summary = '서로 다른 경로가 한 개뿐이라 이 후보를 표시했어요. 다른 길보다 우수하다고 비교한 결과는 아니에요.'
    elif len(eligible) == 1:
        summary = '허용 우회 거리 안의 후보가 한 개뿐이라 추천했어요.'
    elif criteria == ['cctv']:
        summary = f"CCTV 인접 비율이 {best['cctv_percent']:g}%로, 허용 우회 거리 안의 후보 중 가장 높아 추천했어요. 이동 시간은 이 순위에 넣지 않았어요."
    elif criteria == ['light']:
        summary = f"조명 인접 비율이 {best['light_percent']:g}%로, 허용 우회 거리 안의 후보 중 가장 높아 추천했어요. 이동 시간은 이 순위에 넣지 않았어요."
    elif criteria == ['fastest']:
        summary = f"예상 이동 시간이 {best['duration_minutes']:g}분으로, 허용 우회 거리 안에서 가장 짧아 추천했어요. 시설 비율은 이 순위에 넣지 않았어요."
    else:
        summary = ' · '.join(LABELS[c] for c in criteria) + f"을 같은 비중으로 비교한 점수가 {best['criteria_score']:.1f}점으로 가장 높아 추천했어요. 안전 점수는 아니에요."
    if len(tied) > 1:
        summary += ' 같은 점수는 더 짧은 거리를 먼저 고르고, 거리도 같으면 경로 식별자 순으로 정해요.'
    excluded = [r for r in routes if not r['eligible_for_recommendation']]
    maximum = result['parameters'].get('max_detour')
    scope = (f'최단 거리의 {maximum:g}배 이내 후보에서 추천해요.' if maximum is not None
             else '허용 우회 거리 안의 후보에서 추천해요.')
    if excluded:
        scope += f' 한도를 넘은 {len(excluded)}개 후보는 시설 비율이 높아도 추천에서 제외했어요.'
    result['recommendation_explanation'] = {'summary': summary, 'scope': scope,
        'eligible_count': len(eligible), 'excluded_count': len(excluded), 'tied_count': len(tied)}
    for row in routes:
        row['recommendation_status_reason'] = (
            '허용 우회 거리를 넘어 추천에서 제외했어요.' if not row['eligible_for_recommendation']
            else summary if row['id'] == best['id'] else '선택 기준 점수 또는 동점 처리 순서에 따라 다른 후보를 추천했어요.')
    result['selected_criteria'] = criteria
    result['parameters'].update(criteria_weights={c: 1 / len(criteria) for c in criteria},
        ranking_method='selected_criteria_equal_mean', legacy_comparison_cost_used_for_ranking=False)
    result['reason'] += ' 선택한 기준: ' + ' · '.join(LABELS[c] for c in criteria) + '.'
    result['reason'] += ' 선택한 기준만 같은 비중으로 비교했습니다. 이동 시간은 가장 빠른 적격 후보 대비 비율, 시설은 길이 중 인접 비율을 사용합니다. 이 점수는 안전 확률이 아닙니다.'
    return result
