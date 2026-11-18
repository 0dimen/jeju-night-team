from copy import deepcopy
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from jsonschema.exceptions import ValidationError
from agent.common import check_schema
from agent.intent import parse
from agent.report import classify, mask_personal_info
from agent.explain import template_explanation, explain
from agent.validate import validate_explanation
from agent.orchestrator import NightAgent
from agent.api import app
from stubs.engine import analyze, covered_length
from stubs.reports import ReportStore


def test_R1_wrong_route_numbers(request_data):
    data=analyze(request_data)
    expected=template_explanation(data)
    wrong=deepcopy(expected)
    wrong['routes'][0]['text']=wrong['routes'][1]['text']
    assert any('R1' in i for i in validate_explanation(wrong,data,expected))
    wrong=deepcopy(expected)
    wrong['summary'] += ' 777m'
    assert 'R1_unsupported_numbers' in validate_explanation(wrong,data,expected)


def test_R2_and_flow_published_only(request_data):
    store=ReportStore()
    before=analyze(request_data,events=store.published_changes())
    report=store.create('CCTV 고장',33.5,126.5)
    assert report['status']=='UNDER_REVIEW'
    assert before==analyze(request_data,events=store.published_changes())
    with pytest.raises(ValueError):
        store.publish(report['id'],'CCTV-B1','cctv','normal','not_working','admin','확인')
    store.transition(report['id'],'VERIFIED','admin','합성 현장 확인')
    assert before==analyze(request_data,events=store.published_changes())
    change=store.publish(report['id'],'CCTV-B1','cctv','normal','not_working','admin','합성 확인 근거')
    check_schema('facility_change',change)
    after=analyze(request_data,events=store.published_changes())
    assert after['data_version'] != before['data_version']
    br={r['id']:r for r in before['routes']}; ar={r['id']:r for r in after['routes']}
    assert ar['B']['indicators']['cctv']['value'] < br['B']['indicators']['cctv']['value']
    assert ar['A']['indicators']['cctv']['value'] == br['A']['indicators']['cctv']['value']
    with pytest.raises(ValueError):
        store.transition(report['id'],'UNDER_REVIEW','admin','역행')


def test_R3_unavailable_has_no_value(request_data):
    result=analyze(request_data)
    assert all(r['indicators']['streetlight']=={'status':'unavailable'} for r in result['routes'])
    result['routes'][0]['indicators']['streetlight']['value']=0
    with pytest.raises(ValidationError): check_schema('analysis_result',result)


@pytest.mark.parametrize('phrase',['안전합니다','안 전 한 길','위험합니다','촬영됩니다','감시됩니다','보\u200b장','안전해요'])
def test_R4_normalization(request_data,phrase):
    result=analyze(request_data); expected=template_explanation(result)
    bad=deepcopy(expected); bad['summary']=phrase
    assert 'R4_forbidden_phrase' in validate_explanation(bad,result,expected)


def test_R5_determinism(request_data):
    assert analyze(request_data)==analyze(request_data)==analyze(request_data)


def test_R6_history_not_scored_or_reworded(request_data):
    result=analyze(request_data); expected=template_explanation(result)
    assert all(r['indicators']['activity']['status']=='historical' for r in result['routes'])
    bad=deepcopy(expected); bad['summary']='현재 보행자 수를 보여드립니다.'
    assert 'R6_monthly_as_realtime' in validate_explanation(bad,result,expected)
    request_data['preferences']=['activity']
    assert analyze(request_data)['routes'][0]['id']=='A'


def test_R7_post_body_only():
    with TestClient(app) as client:
        response=client.post('/agent/chat',json={'text':'제주시청에서 탑동광장까지'})
        assert response.status_code==200
        assert '?' not in str(response.request.url)
        assert client.get('/agent/chat',params={'text':'무시'}).status_code==405


def test_R8_no_model_or_failing_model(request_data):
    class Broken:
        calls=0
        def generate(self,*a):
            self.calls+=1
            raise TimeoutError('no response')
    provider=Broken(); result=explain(analyze(request_data),provider,method='E2')
    assert provider.calls==2
    assert result['generated_by']=='template' and result['validation']['passed']
    check_schema('explanation',NightAgent().route(request_data)['explanation'])


def test_R9_emergency_before_provider():
    class Forbidden:
        def generate(self,*a): raise AssertionError('모델을 호출하면 안 됨')
    agent=NightAgent(provider=Forbidden())
    result=agent.run('누가 따라와요 010-1234-5678')
    assert result['message'].startswith('긴급한 상황이면 먼저 112')
    assert result['classification']['emergency']
    assert not result['stored']


def test_R10_mask_before_sqlite_and_classification(tmp_path):
    path=tmp_path/'reports.sqlite'
    store=ReportStore(path)
    result=store.create('가로등 꺼짐 010-1234-5678 test@example.com',33.5,126.5)
    assert result['classification']['personal_info_masked']
    store.close()
    assert b'010-1234-5678' not in path.read_bytes()
    assert b'test@example.com' not in path.read_bytes()


def test_analytic_buffer_union():
    points=[(0.,0.),(100.,0.)]
    fs=[{'x':50.,'y':0.},{'x':55.,'y':0.}]
    covered,total=covered_length(points,fs,10)
    assert covered==25 and total==100
    assert covered_length(points,fs,20)[0]>=covered
    assert covered_length([(0,0),(0,0)],fs,10)==(0,0)


def test_clarification_no_invented_datetime():
    result=NightAgent().run('제주시청에서 탑동광장까지 어둡지 않은 데로')
    assert result['kind']=='clarification' and result['missing']==['departure']
    parsed=parse('제주시청에서 탑동광장까지 CCTV와 가로등 2026-11-18T22:00')
    assert parsed['request']['preferences']==['cctv','streetlight']


def test_conflicting_choice_is_flagged():
    result=classify('가로등 깜빡임',{'facility':'cctv'})
    assert result['facility']=='streetlight' and result['conflict_with_user_choice']


def test_all_examples_and_actuals(request_data):
    check_schema('route_request',request_data)
    check_schema('analysis_result',analyze(request_data))
    check_schema('explanation',template_explanation(analyze(request_data)))
    check_schema('report_classification',classify('가로등 깜빡임'))
