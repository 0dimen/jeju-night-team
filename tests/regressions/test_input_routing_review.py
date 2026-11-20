from copy import deepcopy
from fastapi.testclient import TestClient
from agent.api import app
from agent.intent import parse

POINT={'name':'SYNTHETIC 지점','lat':33.5,'lng':126.5}
PENDING={'request':{'origin':POINT,'destination':POINT},'awaiting_route':True}


def test_source_wording_answers_without_time_or_page_location():
    from agent.api import agent
    from unittest.mock import patch
    with TestClient(app) as client,patch.object(agent,'route',side_effect=AssertionError('no route calculation')):
        for text in ['CCTV 정보는 어디서 가져왔고 언제 조사한 거예요?', '가로등 정보가 언제 조사된 건지 알려줘']:
            result=client.post('/agent/conversation',json={'text':text,'state':PENDING}).json()
            assert result['kind']=='data_question' and result['state']=={}
            assert 'missing' not in result and 'SYNTHETIC 지점' not in str(result)


def test_explicit_booking_action_is_not_a_route_even_in_pending_conversation():
    with TestClient(app) as client:
        for text in ['오늘 밤 제주에서 서울 가는 항공권 예약해줘','제주공항에서 동문시장까지 택시 예약해주세요']:
            result=client.post('/agent/conversation',json={'text':text,'state':PENDING}).json()
            assert result['kind']=='unsupported' and result['state']=={}
            assert result['stored'] is False and 'missing' not in result


def test_booking_mention_alone_does_not_block_walking_route():
    assert parse('호텔 예약해뒀어요. 제주시청에서 동문시장까지 걸어가는 길 알려줘')['kind']=='route'
    assert parse('예약한 호텔에서 동문시장까지 걸어갈래')['kind']=='route'


def test_ambiguous_report_returns_questions_without_storing():
    from agent.api import agent
    before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    cases=[('CCTV 고장은 아니고 쓰레기가 있어요','meaning'),
           ('CCTV와 가로등이 모두 고장 났어요','facility'),
           ('CCTV가 어두워요','meaning')]
    with TestClient(app) as client:
        for text,field in cases:
            result=client.post('/agent/conversation',json={'text':text,'state':PENDING}).json()
            assert result['kind']=='report_preview' and result['needs_clarification'] is True
            assert result['stored'] is False and result['state']=={}
            assert any(q['field']==field for q in result['questions'])
            assert 'SYNTHETIC 지점' not in str(result)
    assert before==agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]


def test_emergency_still_precedes_source_and_booking():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':'누가 따라와요. 항공권 예약해줘','state':PENDING}).json()
    assert result['kind']=='emergency' and result['state']=={}


def test_source_question_does_not_validate_unneeded_bad_location_state():
    with TestClient(app) as client:
        result=client.post('/agent/conversation',json={'text':'CCTV 정보는 어디서 가져왔어요?','state':{'request':'invalid'}})
    assert result.status_code==200 and result.json()['kind']=='data_question'
