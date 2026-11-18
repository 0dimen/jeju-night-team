"""사용자 선택은 허용된 문자열이어야 하며 잘못된 입력은 저장하지 않는다."""
import pytest
from fastapi.testclient import TestClient
from agent.api import app,agent
from agent.orchestrator import NightAgent


@pytest.mark.parametrize('choice',[
    {'facility':['cctv']}, {'problem':{'value':'not_working'}},
    {'facility':33}, {'problem':True}, {'facility':'알 수 없음'},
])
def test_invalid_choice_is_client_error_without_storage(choice):
    before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    with TestClient(app,raise_server_exceptions=False) as client:
        result=client.post('/agent/chat',json={'text':'CCTV 고장 제보',
            'context':{'lat':33.5,'lng':126.5,'user_choice':choice}})
    assert result.status_code==422
    after=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    assert after==before


def test_emergency_precedes_invalid_user_choice():
    result=NightAgent().run('누가 따라와요',{'user_choice':{'facility':['cctv']}})
    assert result['kind']=='emergency' and result['stored'] is False
    assert result['message'].startswith('긴급한 상황이면 먼저 112')
