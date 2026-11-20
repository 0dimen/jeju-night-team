from copy import deepcopy
import pytest
from agent.data.foot_route_import import prepare_foot_candidates

def response(points=None):
    return {'code':'Ok','routes':[{'duration':120,'distance':150,'geometry':{'type':'LineString','coordinates':points or [[126.5,33.5],[126.501,33.5]]},'legs':[{'steps':[{'mode':'walking'}]}]}]}

def pair():return [response(),response([[126.5,33.5],[126.501,33.501],[126.501,33.5]])]

def test_real_candidate_keeps_origin_and_limits():
    data=prepare_foot_candidates(pair(),'2026-11-18')
    assert data['properties']['synthetic'] is False
    assert data['properties']['rights_confirmed'] is False
    assert len(data['features'])==2 and all(f['properties']['onsite_checked'] is False for f in data['features'])

def test_duplicate_path_does_not_count_as_two():
    with pytest.raises(ValueError):prepare_foot_candidates([response(),response()],'2026-11-18')

def test_driving_step_rejected():
    data=pair();data[0]['routes'][0]['legs'][0]['steps'][0]['mode']='driving'
    with pytest.raises(ValueError):prepare_foot_candidates(data,'2026-11-18')

def test_changed_endpoint_not_silently_snapped():
    data=pair();data[1]['routes'][0]['geometry']['coordinates'][-1]=[126.502,33.5]
    with pytest.raises(ValueError):prepare_foot_candidates(data,'2026-11-18')

def test_missing_mode_evidence_or_wrong_profile_rejected():
    with pytest.raises(ValueError):prepare_foot_candidates(pair(),'2026-11-18',profile='car')
    data=pair();data[0]['routes'][0]['legs']=[]
    with pytest.raises(ValueError):prepare_foot_candidates(data,'2026-11-18')
