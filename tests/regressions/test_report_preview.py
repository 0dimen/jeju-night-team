from fastapi.testclient import TestClient
from agent.api import app
from agent.report.preview import preview_report


def test_multi_facility_asks_without_storing():
    result=preview_report('CCTV와 가로등이 고장 났어요')
    assert result['stored'] is False and result['requires_human_review'] is True
    assert any(q['field']=='facility' and len(q.get('mentioned_candidates',[]))==2 for q in result['questions'])


def test_negation_is_question_not_approved_classification():
    result=preview_report('CCTV 고장은 아니고 쓰레기가 있어요')
    assert result['stored'] is False
    assert any(q['field']=='meaning' for q in result['questions'])


def test_cctv_darkness_does_not_resolve_meaning():
    result=preview_report('CCTV가 어두워요')
    assert any('영상' in q['message'] for q in result['questions'])


def test_emergency_precedes_invalid_choice():
    result=preview_report('누가 따라와요',{'facility':['invalid']})
    assert result['kind']=='emergency' and result['stored'] is False


def test_preview_api_masks_synthetic_phone_and_does_not_persist():
    from agent.api import agent
    before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    with TestClient(app) as client:
        result=client.post('/reports/preview',json={'text':'CCTV 고장 010-0000-0000'}).json()
    assert '010-0000-0000' not in str(result) and result['stored'] is False
    assert before==agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]


def test_invalid_enum_rejected():
    with TestClient(app) as client:
        response=client.post('/reports/preview',json={'text':'CCTV 고장','user_choice':{'facility':'unknown'}})
    assert response.status_code==422
