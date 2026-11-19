"""선택 기준의 손계산, 미선택 기준 불변성, API 조합 전송 계약."""
from copy import deepcopy
from itertools import combinations

import pytest
from fastapi.testclient import TestClient
from agent.api import app
from agent.data.route_criteria import normalize_criteria, rank_selected_criteria


def baseline():
    return {'routes': [dict(id=rid, duration_minutes=minutes, distance_m=distance,
        cctv_percent=cctv, light_percent=light, eligible_for_recommendation=True)
        for rid, minutes, distance, cctv, light in [
            ('A', 10, 100, 20, 20), ('B', 15, 130, 90, 20), ('C', 15, 130, 20, 90)]],
        'parameters': {}, 'reason': '합성 후보.', 'recommended_route_id': 'A'}


@pytest.mark.parametrize('criteria,winner', [(['fastest'], 'A'), (['cctv'], 'B'), (['light'], 'C'),
    (['fastest','cctv'], 'B'), (['fastest','light'], 'C'), (['cctv','light'], 'B'),
    (['fastest','cctv','light'], 'B')])
def test_all_seven_combinations_use_only_selected_criteria(criteria,winner):
    result = rank_selected_criteria(baseline(), criteria)
    assert result['recommended_route_id'] == winner
    assert set(result['parameters']['criteria_weights']) == set(criteria)
    assert sum(result['parameters']['criteria_weights'].values()) == pytest.approx(1)
    assert result['parameters']['legacy_comparison_cost_used_for_ranking'] is False


def test_manual_mean_and_unselected_metric_invariance():
    result = rank_selected_criteria(baseline(), ['fastest','cctv'])
    assert result['routes'][1]['criteria_score'] == pytest.approx((10/15+.9)/2*100)
    changed=baseline();changed['routes'][0]['light_percent']=100
    assert rank_selected_criteria(changed,['fastest','cctv'])['recommended_route_id']=='B'


def test_detour_exclusion_and_selection_order_and_ties():
    data=baseline();data['routes'][1]['eligible_for_recommendation']=False
    assert rank_selected_criteria(data,['cctv'])['recommended_route_id']=='A'
    a=rank_selected_criteria(baseline(),['light','cctv'])
    data=baseline();data['routes'].reverse()
    b=rank_selected_criteria(data,['cctv','light'])
    assert a['recommended_route_id']==b['recommended_route_id']=='B'
    assert a['selected_criteria']==b['selected_criteria']


@pytest.mark.parametrize('criteria',[[],['both'],['fastest','fastest'],['cctv',False],None])
def test_invalid_or_empty_criteria_rejected(criteria):
    with pytest.raises(ValueError):normalize_criteria(criteria)


def test_api_passes_every_combination_and_old_request_still_works(monkeypatch):
    import agent.data.selected_routes as selected
    calls=[]
    monkeypatch.setattr(selected,'selected_compare',lambda *args,**kwargs: calls.append(kwargs) or {'synthetic':True})
    body={'origin':{'lng':126.49,'lat':33.49},'destination':{'lng':126.491,'lat':33.49},'departure':'2026-11-20T22:00'}
    client=TestClient(app)
    assert client.post('/research/routes/selected',json=body).status_code==200
    assert calls[-1]=={}
    for count in (1,2,3):
        for combo in combinations(('fastest','cctv','light'),count):
            response=client.post('/research/routes/selected',json={**body,'criteria':list(combo)})
            assert response.status_code==200 and calls[-1]['criteria']==list(combo)
    assert client.post('/research/routes/selected',json={**body,'criteria':[]}).status_code==422


def test_selected_route_rejects_bad_selection_before_loading_data(monkeypatch):
    from agent.data.selected_routes import selected_compare
    import agent.data.selected_routes as selected
    def forbidden(*args):raise AssertionError('외부 계산 전에 거부해야 함')
    monkeypatch.setattr(selected,'selected_context',forbidden)
    with pytest.raises(ValueError):
        selected_compare([126.49,33.49],[126.491,33.49],'2026-11-20T22:00',criteria=['cctv','cctv'])


def test_selected_route_integration_ranks_combination(monkeypatch):
    from types import SimpleNamespace
    import agent.data.selected_routes as selected
    monkeypatch.setattr(selected,'selected_context',lambda *a:SimpleNamespace())
    monkeypatch.setattr(selected,'compare',lambda *a:{**baseline(),'limitations':[]})
    monkeypatch.setattr(selected,'public_points',lambda *a:[])
    result=selected.selected_compare([126.49,33.49],[126.491,33.49],'2026-11-20T22:00',criteria=['fastest','cctv'])
    assert result['recommended_route_id']=='B'
    assert result['selected_criteria']==['fastest','cctv']


def test_cctv_priority_over_shorter_distance_regression():
    # 기존식: 100*(1+4*.9)=460, 120*(1+4*.8)=504 → A.
    # CCTV 단독 선택의 새 계약은 20%인 B를 고른다.
    data=baseline();data['routes']=data['routes'][:2]
    data['routes'][0].update(cctv_percent=10,distance_m=100)
    data['routes'][1].update(cctv_percent=20,distance_m=120)
    result=rank_selected_criteria(data,['cctv'])
    assert result['recommended_route_id']=='B'
    summary=result['recommendation_explanation']['summary']
    assert '20%' in summary and '이동 시간은 이 순위에 넣지 않았어요' in summary


def test_higher_coverage_but_detour_exclusion_is_explained():
    data=baseline();data['parameters']['max_detour']=1.5
    data['routes'][1]['eligible_for_recommendation']=False
    result=rank_selected_criteria(data,['cctv'])
    assert result['recommended_route_id']=='A'
    explanation=result['recommendation_explanation']
    assert explanation['excluded_count']==1 and '1.5배' in explanation['scope']
    assert '시설 비율이 높아도 추천에서 제외' in explanation['scope']
    assert '추천에서 제외' in result['routes'][1]['recommendation_status_reason']


def test_only_candidate_is_not_claimed_superior_and_tie_disclosed():
    data=baseline();data['routes']=data['routes'][:1]
    explanation=rank_selected_criteria(data,['cctv'])['recommendation_explanation']
    assert '다른 길보다 우수하다고 비교한 결과는 아니에요' in explanation['summary']
    result=rank_selected_criteria(baseline(),['cctv','light'])
    assert result['recommendation_explanation']['tied_count']==2
    assert '같은 점수' in result['recommendation_explanation']['summary']
