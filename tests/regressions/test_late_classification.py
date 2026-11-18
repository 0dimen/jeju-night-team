"""늦은 모델 응답이 검증된 분류를 덮어쓰지 않아야 한다. 모두 합성 검토다."""
from copy import deepcopy
import json
import pytest
from agent.orchestrator import NightAgent
from agent.report import classify
from stubs.reports import ReportStore


@pytest.mark.parametrize('state',['VERIFIED','REJECTED','PUBLISHED'])
def test_closed_review_classification_cannot_be_replaced(state):
    store=ReportStore();row=store.create('SYNTHETIC CCTV 고장',33.5,126.5)
    store.transition(row['id'],'VERIFIED' if state=='PUBLISHED' else state,'SYNTHETIC-admin','합성 확인')
    if state=='PUBLISHED':
        store.publish(row['id'],'CCTV-B1','cctv','normal','not_working','SYNTHETIC-admin','합성 게시')
    before=store.get(row['id'])
    with pytest.raises(ValueError):
        store.update_classification(row['id'],classify('SYNTHETIC 보행로 막힘'))
    assert store.get(row['id'])==before
    store.close()


def test_late_model_prediction_preserves_reviewed_result_and_masking():
    store=ReportStore();reviewed=[]
    class LateModel:
        def generate(self,task,payload):
            assert task=='report' and '010-0000-0000' not in json.dumps(payload)
            rid=store.db.execute('SELECT id FROM reports').fetchone()['id']
            reviewed.append(deepcopy(store.get(rid)['classification']))
            store.transition(rid,'VERIFIED','SYNTHETIC-admin','모델 응답 전 합성 검토')
            return classify('SYNTHETIC 보행로 막힘')
    agent=NightAgent({'structure':'S1','intent':'I1','explain':'E1'},LateModel(),store)
    result=agent.run('SYNTHETIC CCTV 고장 제보 010-0000-0000',{'lat':33.5,'lng':126.5})
    assert result['kind']=='report' and result['stored']
    assert result['report']['status']=='VERIFIED'
    assert result['report']['classification']==reviewed[0]
    assert result['report']['classification']['facility']=='cctv'
    assert result['report']['classification']['personal_info_masked']
    assert '010-0000-0000' not in json.dumps(result)
    store.close()
