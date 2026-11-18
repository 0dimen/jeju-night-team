import csv
import json
import numpy as np
import pytest
from discovery.catalog import CatalogSearch
from discovery.results import experiment_summaries
from fastapi.testclient import TestClient
from discovery.api import app


class Encoder:
    def encode(self,texts): return np.array([[1.,0.] for _ in texts])


def test_candidates_never_adopt_or_change_registry(tmp_path):
    path=tmp_path/'catalog.csv'
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['title','approve']);writer.writeheader()
        writer.writerows([{'title':'SYNTHETIC 시설 위치','approve':''},{'title':'SYNTHETIC 농산물','approve':''}])
    vectors=tmp_path/'vectors.npy'; np.save(vectors,np.array([[1.,0.],[0.,1.]]))
    search=CatalogSearch(Encoder(),path,vectors)
    result=search.search('합성 경로 시설',1)
    assert not result['adopted'] and result['status']=='candidate_only'
    assert result['candidates'][0]['title']=='SYNTHETIC 시설 위치'
    assert result['candidates'][0]['approve']==''
    with pytest.raises(ValueError): search.search('')


def test_empty_results_are_explicit(tmp_path):
    result=experiment_summaries(tmp_path)
    assert result['results']==[] and result['data']=='SYNTHETIC'


def test_query_endpoint_uses_post_body():
    with TestClient(app) as client:
        assert client.get('/data/candidates',params={'query':'미전송'}).status_code==405
        response=client.get('/experiments/results')
        assert response.status_code==200 and 'oracle' in response.json()


def test_missing_catalog_model_returns_unavailable(monkeypatch):
    import discovery.api as api
    def missing():
        raise FileNotFoundError('SYNTHETIC missing local model')
    monkeypatch.setattr(api,'catalog',missing)
    with TestClient(app,raise_server_exceptions=False) as client:
        response=client.post('/data/candidates',json={'query':'합성 시설 자료'})
    assert response.status_code==503
    assert '먼저 준비' in response.json()['detail']


def test_blank_catalog_query_is_rejected_before_model(monkeypatch):
    import discovery.api as api
    def unexpected():
        raise AssertionError('빈 검색에서 모델을 준비하면 안 됨')
    monkeypatch.setattr(api,'catalog',unexpected)
    with TestClient(app,raise_server_exceptions=False) as client:
        response=client.post('/data/candidates',json={'query':'   '})
    assert response.status_code==422


def test_encoder_checks_missing_model_before_onnx(tmp_path):
    from agent.intent.embedding import SentenceEncoder
    with pytest.raises(FileNotFoundError):
        SentenceEncoder(tmp_path)


def test_partial_or_outside_result_files_do_not_break_results(tmp_path):
    for name,content in [('unfinished','{"summary":'),('outside','{"summary":"/etc/passwd"}'),
                         ('missing','{"summary":"not-present.json"}')]:
        folder=tmp_path/name;folder.mkdir();(folder/'latest.json').write_text(content)
    result=experiment_summaries(tmp_path)
    assert result['results']==[]
    assert result['incomplete_results']==3


def test_partial_results_expose_denominators_code_phase_and_cost_limits(tmp_path):
    folder=tmp_path/'SYNTHETIC_partial';folder.mkdir()
    summary=folder/'summary.json';summary.write_text('{}')
    canonical={'name':'SYNTHETIC_partial','status':'paused_budget','source_phase':'post_report_v7',
               'release_candidate':True,'observations':46,'unique_cases':42,'metrics_revision':4,
               'paid_estimate_usd':None,'cost_status':'로컬: API 비용 없음; 전력 미측정',
               'tasks':{'intent':{'scored_cases':41}},'output_and_thinking_tokens':0}
    (folder/'analysis_v2.json').write_text(json.dumps(canonical))
    (folder/'latest.json').write_text(json.dumps({'summary':str(summary)}))
    result=experiment_summaries(tmp_path)['results'][0]
    for key in ('status','source_phase','release_candidate','observations','unique_cases',
                'paid_estimate_usd','cost_status','metrics_revision','output_and_thinking_tokens'):
        assert result[key]==canonical[key]
    assert result['tasks']['intent']['scored_cases']==41
