from copy import deepcopy
import pytest
from agent.data.route_score_proposal import compare_proposals

PROFILES={'시간':[.6,.2,.2],'CCTV':[.2,.6,.2],'조명':[.2,.2,.6]}
ROUTES=[{'id':'A','minutes':10,'cctv_fraction':.2,'light_fraction':.2},
        {'id':'B','minutes':15,'cctv_fraction':.9,'light_fraction':.2},
        {'id':'C','minutes':15,'cctv_fraction':.2,'light_fraction':.9}]


def test_three_formulas_can_select_different_routes_without_changing_input():
    before=deepcopy(ROUTES)
    result=compare_proposals(ROUTES,PROFILES)
    assert [r['tied_winner_ids'] for r in result['rankings'].values()]==[['A'],['B'],['C']]
    assert result['distinct_winner_count']==3 and ROUTES==before
    assert result['operational_policy_changed'] is False


def test_identical_winners_not_forced_into_three_fake_recommendations():
    routes=deepcopy(ROUTES);routes[0].update(cctv_fraction=1,light_fraction=1)
    result=compare_proposals(routes,PROFILES)
    assert result['distinct_winner_count']==1
    assert all(row['tied_winner_ids']==['A'] for row in result['rankings'].values())


def test_uses_fastest_three_only_from_provided_candidates_and_preserves_ties():
    routes=deepcopy(ROUTES)+[{'id':'D','minutes':100,'cctv_fraction':1,'light_fraction':1}]
    assert compare_proposals(routes,PROFILES)['selected_ids']==['A','B','C']
    routes=[{'id':k,'minutes':10,'cctv_fraction':.5,'light_fraction':.5} for k in 'ABC']
    assert all(rank['tied_winner_ids']==['A','B','C'] for rank in compare_proposals(routes,PROFILES)['rankings'].values())


@pytest.mark.parametrize('field,value',[('cctv_fraction',None),('light_fraction',float('nan')),('minutes',0),('minutes',True),('cctv_fraction',1.1)])
def test_missing_or_invalid_not_imputed_as_zero(field,value):
    routes=deepcopy(ROUTES);routes[0][field]=value
    with pytest.raises(ValueError):compare_proposals(routes,PROFILES)


def test_weights_and_candidate_minimum_are_explicit():
    with pytest.raises(ValueError):compare_proposals(ROUTES[:2],PROFILES)
    with pytest.raises(ValueError):compare_proposals(ROUTES,{'one':[1,1,1]})
