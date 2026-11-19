from pathlib import Path
import hashlib
import pytest
from fastapi.testclient import TestClient
from agent.api import app

OPEN=Path('data/open')


def test_missing_research_data_returns_unavailable_without_synthetic_fallback(monkeypatch,tmp_path):
    monkeypatch.setenv('JEJU_OPEN_DATA_DIR',str(tmp_path))
    with TestClient(app) as client:
        response=client.post('/research/routes/facilities',json={'region':'yeondong'})
    assert response.status_code==503 and '합성 결과로 대신하지 않습니다' in response.json()['detail']
    assert str(tmp_path) not in response.text


def test_research_limits_and_arbitrary_region_are_rejected():
    with TestClient(app) as client:
        for body in [{'region':'anywhere'},{'region':'yeondong','weight':-1},{'region':'seogwipo','max_detour':3}]:
            assert client.post('/research/routes/facilities',json=body).status_code==422


@pytest.mark.skipif(not OPEN.exists(),reason='배포본에는 공개 원본이 없음')
def test_real_facility_preference_finds_improvement_and_preserves_sources(monkeypatch):
    monkeypatch.delenv('JEJU_OPEN_DATA_DIR',raising=False)
    path=OPEN/'jeju_city_streetlights_20241010.csv';before=hashlib.sha256(path.read_bytes()).hexdigest()
    with TestClient(app) as client:
        response=client.post('/research/routes/facilities',json={'region':'yeondong','preference':'cctv','weight':4})
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    result=response.json();assert result['synthetic'] is False and result['research_only'] is True
    assert result['sources']['cctv']['selected_rows']==937
    assert result['sources']['cctv']['purposes']==['생활방범','교통단속','어린이보호','시설물관리']
    base,preferred=result['routes'];assert base['coordinates'][0]==preferred['coordinates'][0] and base['coordinates'][-1]==preferred['coordinates'][-1]
    assert preferred['cctv_percent']>base['cctv_percent']
    assert preferred['distance_m']<=base['distance_m']*1.5
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


@pytest.mark.skipif(not OPEN.exists(),reason='배포본에는 공개 원본이 없음')
def test_same_best_route_not_presented_as_fake_second_option(monkeypatch):
    monkeypatch.delenv('JEJU_OPEN_DATA_DIR',raising=False)
    with TestClient(app) as client:
        result=client.post('/research/routes/facilities',json={'region':'seogwipo','preference':'both'}).json()
    assert result['same_route'] is True and len(result['routes'])==1


def test_raw_open_data_is_not_a_web_static_directory():
    with TestClient(app) as client:
        assert client.get('/data/open/jeju_cctv_mois_standard.csv').status_code==404
