"""원본 제거 배포에서도 동일한 계산·상태·비공개 경로를 유지하는지 검사."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agent.api import app
from scripts.build_vercel_data import build
from agent.data.research_router import get_router

pytestmark=pytest.mark.skipif(not Path('data/open').exists(),reason='원본 없는 배포에서는 별도 패키지 검증')


def test_compiled_matches_source_for_preferences_and_radius(tmp_path,monkeypatch):
    manifest=build(tmp_path)
    assert len(manifest)==4 and sum(m['bytes'] for m in manifest)<10_000_000
    for region in ('yeondong','seogwipo'):
        for source in ('standard','datahub'):
            for preference,radius in [('fastest',50),('cctv',50),('light',200),('both',200)]:
                monkeypatch.delenv('JEJU_COMPILED_DATA_DIR',raising=False)
                expected=get_router(region,source).route(preference,cctv_radius=radius)
                monkeypatch.setenv('JEJU_COMPILED_DATA_DIR',str(tmp_path))
                actual=get_router(region,source).route(preference,cctv_radius=radius)
                assert expected==actual


def test_compiled_api_without_original_and_no_raw_routes(tmp_path,monkeypatch):
    build(tmp_path)
    monkeypatch.setenv('JEJU_COMPILED_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('JEJU_OPEN_DATA_DIR',str(tmp_path/'absent'))
    c=TestClient(app)
    response=c.post('/research/agent/conversation',json={'text':'연동 공개 구간 2026-11-20 오후 9시'})
    assert response.status_code==200 and response.json()['synthetic'] is False
    status=c.get('/runtime/status');assert status.headers['Cache-Control']=='no-store'
    assert status.json()['facility_data_connected'] and not status.json()['external_llm_enabled']
    assert c.get('/').status_code==200
    for path in ('/runtime/facilities/yeondong_standard.json','/data/open/jeju_cctv_mois_standard.csv','/.env'):
        assert c.get(path).status_code==404


def test_global_facilities_match_original_selection(tmp_path,monkeypatch):
    import json
    from agent.data.selected_routes import load_facilities
    build(tmp_path)
    for source,count in [('standard',937),('datahub',473)]:
        monkeypatch.delenv('JEJU_COMPILED_DATA_DIR',raising=False)
        original=load_facilities(source)
        monkeypatch.setenv('JEJU_COMPILED_DATA_DIR',str(tmp_path))
        compiled=load_facilities(source)
        assert len(compiled[0])==89933 and len(compiled[1])==count
        assert json.dumps(original,sort_keys=True)==json.dumps(compiled,sort_keys=True)
