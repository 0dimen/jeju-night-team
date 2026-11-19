import json
from pathlib import Path
from fastapi.testclient import TestClient
from agent.api import app,agent

ITEMS={row['id']:row['text'] for row in json.loads(Path('review/received_sentences/drive15_INPUTS.json').read_text())}


def test_received_urgent_route_is_emergency_without_saving_or_questions():
    with TestClient(app) as client:
        for rid in ('11','12'):
            response=client.post('/agent/conversation',json={'text':ITEMS[rid],'state':{}}).json()
            assert response['kind']=='emergency' and response['stored'] is False and response['state']=={}
            assert 'missing' not in response


def test_external_repair_request_not_saved_or_forwarded():
    before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':ITEMS['15']}).json()
    assert result['kind']=='unsupported' and result['stored'] is False and '외부 기관' in result['message']
    assert agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==before


def test_received_walkway_obstruction_and_unknown_location_remain_preview():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':ITEMS['08']}).json()
        assert result['classification_candidate']['facility']=='walkway'
        assert result['classification_candidate']['problem']=='obstructed'
        assert result['stored'] is False and any(q['field']=='location' for q in result['questions'])
        unknown=client.post('/agent/conversation',json={'text':ITEMS['10']}).json()
        assert unknown['classification_candidate']['facility']=='walkway'
        assert any(q['field']=='location' for q in unknown['questions'])


def test_received_half_hour_and_night_preserved_but_date_confirmation_required():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':ITEMS['05']}).json()
    assert result['missing']==['date']
    assert result['state']['hour']==10 and result['state']['minute']==30 and result['state']['period']=='pm'
    assert 'departure' not in result['state']['request']


def test_source_question_discards_page_location_and_no_time_questions():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':ITEMS['13'],'state':{'request':{'origin':{'name':'PRIVATE','lat':33.5,'lng':126.5}}}}).json()
    assert result['kind']=='data_question' and result['state']=={} and 'PRIVATE' not in str(result)



def test_place_only_reply_fills_asked_destination_without_overwriting_origin():
    with TestClient(app) as client:
        first=client.post('/agent/conversation',json={'text':'제주시청에서 집으로 가는 길 알려줘'}).json()
        assert first['missing']==['destination']
        second=client.post('/agent/conversation',json={'text':'탑동광장','state':first['state']}).json()
    assert second['state']['request']['origin']['name']=='제주시청'
    assert second['state']['request']['destination']['name']=='탑동광장'
    assert second['missing']==['date']
