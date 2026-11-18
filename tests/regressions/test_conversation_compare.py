from copy import deepcopy
from fastapi.testclient import TestClient
from agent.api import app
from agent.comparison import comparison_table
from agent.common import ROOT
import json
from stubs.engine import analyze

POINT={'name':'SYNTHETIC 지점','lat':33.5,'lng':126.5}

def test_followup_time_leads_to_comparison_without_model():
    state={'request':{'origin':POINT,'destination':POINT,'preferences':['cctv']},'awaiting_route':True}
    with TestClient(app) as client:
        for text in ['3시','2026-11-19','오후']:
            response=client.post('/agent/conversation',json={'text':text,'state':state})
            assert response.status_code==200
            result=response.json();state=result['state']
    assert result['kind']=='route' and result['synthetic'] is True
    assert state['request']['departure']=='2026-11-19T15:00'
    table=result['comparison_table']
    assert table['recommended_route_id']==table['facility_leader_route_id']=='B'
    assert table['fastest_route_id']=='A'
    assert {r['id']:r['cctv_comparison_value'] for r in table['rows']}=={'A':20.2,'B':45.3}
    assert result['page_location_stored'] is False and response.headers['cache-control']=='no-store'


def test_reset_discards_locations_and_fresh_request_asks_again():
    state={'request':{'origin':POINT,'destination':POINT},'awaiting_route':True}
    with TestClient(app) as client:
        reset=client.post('/agent/conversation',json={'text':'초기화','state':state}).json()
        fresh=client.post('/agent/conversation',json={'text':'집으로 갈거야','state':reset['state']}).json()
    assert reset['state']=={} and reset['kind']=='reset'
    assert fresh['missing']==['destination']


def test_missing_or_pending_values_are_not_zero_scores():
    request=json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text(encoding='utf-8'))
    result=analyze(request)
    for route in result['routes']:route['indicators']['cctv']={'status':'unavailable'}
    table=comparison_table(result)
    assert all(r['cctv_comparison_value'] is None for r in table['rows'])
    assert table['facility_leader_route_id'] is None
    for route in result['routes']:route['indicators']['cctv']={'status':'pending','value':.9}
    assert all(r['cctv_comparison_value'] is None for r in comparison_table(result)['rows'])


def test_comparison_does_not_rewrite_engine_ranking():
    request=json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text(encoding='utf-8'))
    request['preferences']=['none']
    analysis=analyze(request);before=deepcopy(analysis);table=comparison_table(analysis)
    assert table['recommended_route_id']=='A' and table['facility_leader_route_id']=='B'
    assert analysis==before
