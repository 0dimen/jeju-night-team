from copy import deepcopy
from fastapi.testclient import TestClient
from agent.api import app
from agent.conversation import page_turn

POINT={'name':'SYNTHETIC 위치','lat':33.5,'lng':126.5}


def located():return {'request':{'origin':POINT,'destination':POINT},'awaiting_route':True}


def test_date_and_period_are_confirmed_without_clock_guess():
    result=page_turn('3시에 갈거야',located())
    assert result['missing']==['date']
    result=page_turn('2026-11-19',result['state'])
    assert result['missing']==['period']
    result=page_turn('오후',result['state'])
    assert result['kind']=='route_ready' and result['request']['departure']=='2026-11-19T15:00'


def test_morning_midnight_noon():
    for hour,period,expected in [(12,'오전','00'),(12,'오후','12'),(3,'오전','03')]:
        result=page_turn(f'2026-11-19 {period} {hour}시',located())
        assert result['request']['departure']==f'2026-11-19T{expected}:00'


def test_new_page_does_not_inherit_home():
    with TestClient(app) as client:
        first=client.post('/agent/conversation',json={'text':'집으로 갈거야','state':located()}).json()
        second=client.post('/agent/conversation',json={'text':'집으로 갈거야'}).json()
    assert 'destination' in first['state']['request']
    assert second['missing']==['destination'] and 'destination' not in second['state']['request']


def test_unrelated_question_does_not_ask_time_or_echo_home():
    with TestClient(app) as client:
        response=client.post('/agent/conversation',json={'text':'데이터 출처 알려줘','state':located()})
    result=response.json()
    assert result.get('missing') is None and result['state']=={}
    assert 'SYNTHETIC 위치' not in str(result)


def test_emergency_clears_page_state_even_if_invalid():
    result=page_turn('누가 따라와요',{'request':'bad'})
    assert result['kind']=='emergency' and result['state']=={}


def test_invalid_time_returns_safe_error():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':'2026-02-30 오후 3시','state':located()})
    assert result.status_code==422 and '33.5' not in result.text


def test_state_not_mutated_or_shared():
    state=located();before=deepcopy(state)
    page_turn('3시',state)
    assert state==before


def test_private_page_state_has_no_cache_or_database_entry():
    from agent.api import agent
    before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    with TestClient(app) as client:
        response=client.post('/agent/conversation',json={'text':'집으로 갈거야','state':located()})
    assert response.headers['cache-control']=='no-store'
    assert agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==before


def test_correcting_hour_does_not_keep_old_departure():
    state=page_turn('2026-11-19 오후 3시',located())['state']
    result=page_turn('4시',state)
    assert result['missing']==['period'] and 'departure' not in result['state']['request']
    result=page_turn('오후',result['state'])
    assert result['request']['departure']=='2026-11-19T16:00'
