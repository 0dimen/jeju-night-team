"""확정 시간 정책·공개 끝점·비저장·미검토 상태에 대한 회귀 검사."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agent.api import app

pytestmark=pytest.mark.skipif(not Path('data/open').exists(),reason='공개 자료는 배포 묶음에서 제외')
c=TestClient(app)
def turn(text,state=None):
    r=c.post('/research/agent/conversation',json={'text':text,'state':state or {}})
    assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    return r.json()

def test_date_and_period_before_real_calculation():
    a=turn('연동 공개 구간을 CCTV 위주로 3시에 갈게요')
    assert a['missing']==['date']
    b=turn('2026-11-20',a['state']);assert b['missing']==['period']
    d=turn('오후',b['state']);assert d['kind']=='facility_routes' and not d['synthetic']
    assert d['departure']=='2026-11-20T15:00' and d['preference']=='cctv'
    assert d['routes'][1]['cctv_percent']>d['routes'][0]['cctv_percent']
    assert 'request' not in d['state']['page'] and not d['stored']
    assert d['routes'][0]['walk_review']['reviewed_segments']==0
    assert all(not s['reviewed'] for row in d['routes'] for s in row['walk_review']['segments'])

def test_home_reverse_unknown_no_synthetic_substitution():
    for text in ('제주대학교에서 집으로 가려고 해','누웨마루에서 삼무공원으로 가고 싶어','서귀포에서 집으로 가고 싶어'):
        r=turn(text);assert r['missing']==['supported_region'] and not r['state']
    a=turn('연동 공개 구간 2026-11-20 오후 9시')
    assert turn('집으로 바꿔줘',a['state'])['missing']==['supported_region']

def test_emergency_reset_source_no_time_questions():
    assert '112' in turn('누가 계속 따라와요')['message']
    assert turn('초기화',{'region':'yeondong'})['state']=={}
    assert turn('CCTV 자료 출처가 뭐야?')['kind']=='data_question'

def test_untrusted_state_locations_not_echoed():
    s={'region':'yeondong','page':{'request':{'origin':{'name':'비공개 집 주소'}}}}
    result=turn('오후 3시',s)
    assert '비공개' not in str(result)

def test_changed_time_requires_period_again():
    a=turn('서귀포 공개 구간 2026-11-20 오후 9시')
    assert a['same_route'] and len(a['routes'])==1
    b=turn('3시',a['state']);assert b['missing']==['period']
    assert turn('오전',b['state'])['departure']=='2026-11-20T03:00'

def test_missing_data_is_503_not_demo(monkeypatch,tmp_path):
    monkeypatch.setenv('JEJU_OPEN_DATA_DIR',str(tmp_path))
    r=c.post('/research/agent/conversation',json={'text':'연동 공개 구간 2026-11-20 오후 9시'})
    assert r.status_code==503 and '합성 경로로 대신하지 않습니다' in r.text


def test_natural_tmap_selection_preserves_date_flow(monkeypatch):
    calls=[]
    def compare(router,preference):
        calls.append(preference);return {**router.route(preference),'provider':'tmap'}
    monkeypatch.setattr('agent.data.tmap_routes.compare',compare)
    a=turn('연동 공개 구간 티맵으로 CCTV 위주로 3시')
    assert a['missing']==['date']
    b=turn('2026-11-20',a['state']);assert b['missing']==['period']
    result=turn('오후',b['state']);assert result['provider']=='tmap' and calls==['cctv']
    back=turn('공개 도로망으로 변경해줘',result['state']);assert back['kind']=='facility_routes' and back.get('provider')!='tmap'
