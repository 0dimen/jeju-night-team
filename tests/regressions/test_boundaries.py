"""지시서 규칙에서 도출한 추가 경계 검사. 실제 출력에 맞춰 답안을 고치지 않는다."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from fastapi.testclient import TestClient
from jsonschema.exceptions import ValidationError
from agent.api import app
from agent.common import check_schema
from agent.report import mask_personal_info
from agent.explain import explain
from stubs.engine import analyze
from stubs.reports import ReportStore


@pytest.mark.parametrize('text',['０１０－００００－００００','010\u200b-0000-0000','010‑0000‑0000'])
def test_R10_unicode_phone_patterns(text):
    masked,changed=mask_personal_info('가로등 꺼짐 '+text)
    assert changed and '[개인정보 가림]' in masked


def test_R4_template_rejects_bad_engine_prose(request_data):
    analysis=analyze(request_data)
    analysis['routes'][0]['indicators']['cctv']['display']='안전합니다'
    try:
        result=explain(analysis,method='E1')
    except ValueError:
        return
    assert '안전합니다' not in json.dumps(result,ensure_ascii=False)


def test_R4_report_does_not_repeat_assertions_as_service_claim():
    from agent.report import classify
    result=classify('가로등 고장입니다. 여기는 위 험 합 니 다. 보장')
    compact=''.join(c for c in result['summary'] if c.isalnum())
    assert '위험합니다' not in compact and '보장' not in compact
    assert result['facility']=='streetlight' and result['problem']=='not_working'


@pytest.mark.parametrize('radius',[float('nan'),float('inf'),-1,0])
def test_engine_rejects_nonfinite_radius(request_data,radius):
    with pytest.raises(ValueError):analyze(request_data,radius=radius)


def change(before='normal',after='not_working',facility='CCTV-B1',kind='cctv'):
    return {'facility_id':facility,'type':kind,'before':before,'after':after,
            'report_id':'SYNTHETIC-RPT-1','verified_by':'synthetic-admin','verified_at':'2026-11-18T03:00:00+09:00'}


def test_generator_events_have_same_version_as_list(request_data):
    events=[change()]
    assert analyze(request_data,events=events)==analyze(request_data,events=(x for x in events))


def test_engine_can_be_replaced_without_changing_agent(request_data):
    from agent.orchestrator import NightAgent
    seen=[]
    def replacement(request,**options):
        seen.append((request,options))
        return analyze(request,**options)
    agent=NightAgent(engine=replacement)
    assert agent.route(request_data)['explanation']['validation']['passed']
    assert seen[0][1]['events']==[] and seen[0][1]['radius']==50


@pytest.mark.parametrize('event',[change(facility='UNKNOWN'),change(kind='streetlight'),change(before='damaged')])
def test_engine_rejects_invalid_facility_change(request_data,event):
    with pytest.raises(ValueError):analyze(request_data,events=[event])


def test_published_transition_requires_change_event():
    store=ReportStore();report=store.create('CCTV 고장',33.5,126.5)
    store.transition(report['id'],'VERIFIED','admin','합성 검증')
    with pytest.raises(ValueError):store.transition(report['id'],'PUBLISHED','admin','이벤트 없이 게시')


def test_store_parallel_reports_are_transactional():
    store=ReportStore()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda i:store.create('가로등 꺼짐 '+str(i),33.5,126.5),range(12)))
    assert len({r['id'] for r in rows})==12
    assert all(r['status']=='UNDER_REVIEW' for r in rows)
    assert store.db.execute('SELECT COUNT(*) FROM history').fetchone()[0]==36


@pytest.mark.parametrize('departure',['2026-02-30T22:00','2026-11-18T99:00','2026-11-18T22:00garbage'])
def test_invalid_calendar_datetime_rejected(request_data,departure):
    request_data['departure']=departure
    with pytest.raises((ValueError,ValidationError)):
        # 실제로 존재하지 않는 날짜가 입력 검사를 통과하지 않아야 한다.
        check_schema('route_request',request_data)


def test_bad_report_location_returns_client_error():
    with TestClient(app,raise_server_exceptions=False) as client:
        result=client.post('/agent/chat',json={'text':'가로등 고장 제보','context':{'lat':'not-a-coordinate','lng':126.5}})
        assert result.status_code==422


def test_invalid_request_does_not_echo_phone_or_forbidden_claim():
    with TestClient(app,raise_server_exceptions=False) as client:
        result=client.post('/agent/chat',json={'text':'위험합니다 010-0000-0000 '+'가'*5001})
    assert result.status_code==422
    assert '010-0000-0000' not in result.text and '위험합니다' not in result.text


def test_emergency_message_precedes_body_validation_error():
    with TestClient(app,raise_server_exceptions=False) as client:
        result=client.post('/agent/chat',json={'text':'누가 따라와요 '+'가'*5001})
    assert result.status_code==200
    assert result.json()['message'].startswith('긴급한 상황이면 먼저 112')


def test_emergency_precedes_invalid_direct_context():
    from agent.orchestrator import NightAgent
    result=NightAgent().run('누가 따라와요',context=['SYNTHETIC 잘못된 문맥'])
    assert result['kind']=='emergency' and result['stored'] is False
    assert result['message'].startswith('긴급한 상황이면 먼저 112')


def test_emergency_direct_report_does_not_validate_facility_first():
    from agent.orchestrator import NightAgent
    result=NightAgent().report('누가 따라와요',user_choice={'facility':['cctv']})
    assert result['kind']=='emergency' and result['stored'] is False
    assert result['message'].startswith('긴급한 상황이면 먼저 112')
