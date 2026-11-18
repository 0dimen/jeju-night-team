from copy import deepcopy
import json
import pytest
pytest.importorskip('pyproj')
from agent.common import ROOT
from agent.data.file_engine import FileRouteEngine
from agent.orchestrator import NightAgent

def fixtures(tmp_path):
    route=json.loads((ROOT/'data/route_examples/SYNTHETIC_routes.geojson').read_text(encoding='utf-8'))
    cctv=json.loads((ROOT/'data/route_examples/SYNTHETIC_cctv.json').read_text(encoding='utf-8'))
    request=json.loads((ROOT/'data/route_examples/SYNTHETIC_file_request.json').read_text(encoding='utf-8'))
    paths=[tmp_path/'routes.json',tmp_path/'cctv.json']
    return route,cctv,request,paths

def make(route,cctv,paths):
    for data,path in zip((route,cctv),paths):path.write_text(json.dumps(data),encoding='utf-8')
    return FileRouteEngine(*paths)

def test_file_geometry_instead_of_fixed_stub(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths);result=engine(request)
    out={r['id']:r for r in result['routes']}
    assert 185<float(out['A']['distance'][:-1])<188
    assert .5<out['A']['indicators']['cctv']['value']<.6
    assert out['B']['indicators']['cctv']['value']==0
    agent=NightAgent(engine=engine)
    assert agent.route(request)['synthetic'] is True
    agent.store.db.close()

def test_mismatched_request_endpoints_rejected(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths);request['origin']['lat']+=.01
    with pytest.raises(ValueError):engine(request)

def test_real_data_requires_rights_and_coordinate_evidence(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path)
    route['properties']['synthetic']=cctv['metadata']['synthetic']=False
    with pytest.raises(ValueError):make(route,cctv,paths)

def test_mixed_real_and_synthetic_is_rejected(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);cctv['metadata']['synthetic']=False
    with pytest.raises(ValueError):make(route,cctv,paths)

def test_missing_facilities_do_not_become_zero_score(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);cctv['rows']=[]
    result=make(route,cctv,paths)(request)
    assert all(r['indicators']['cctv']=={'status':'unavailable'} for r in result['routes'])
    assert 'cctv' in result['unavailable_preferences']

def test_unknown_or_duplicate_facilities_rejected(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);cctv['rows']*=2
    with pytest.raises(ValueError):make(route,cctv,paths)

def test_swapped_axes_not_automatically_fixed(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);r=cctv['rows'][0];r['lat'],r['lng']=r['lng'],r['lat']
    with pytest.raises(ValueError):make(route,cctv,paths)

def test_projected_range_limit_is_explicit(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path)
    for feature in route['features']:feature['geometry']['coordinates'][-1]=[127.56,33.25]
    with pytest.raises(ValueError):make(route,cctv,paths)


def test_row_basis_date_is_not_replaced_by_metadata_date(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);cctv['metadata']['observed_at']='2026-11-18'
    cctv['rows'][0]['basis_date']='2022-12-15'
    engine=make(route,cctv,paths);result=engine(request)
    assert result['sources'][0]['observed_at']=='2022-12-15'
    agent=NightAgent(engine=engine);output=agent.route(request);agent.store.db.close()
    assert any('과거 기준일 자료' in r['text'] for r in output['explanation']['routes'])


def test_only_published_changes_affect_file_metrics(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths);agent=NightAgent(engine=engine)
    before=agent.route(request)['analysis']
    report=agent.store.create('SYNTHETIC CCTV 고장',33.25,126.561)
    assert agent.route(request)['analysis']==before
    agent.store.transition(report['id'],'VERIFIED','SYNTHETIC reviewer','가상 확인')
    assert agent.route(request)['analysis']==before
    agent.store.publish(report['id'],'SYNTHETIC-F1','cctv','normal','not_working','SYNTHETIC reviewer','가상 게시')
    after=agent.route(request)['analysis'];agent.store.db.close()
    assert after['data_version']!=before['data_version']
    assert all(r['indicators']['cctv']['value']==0 for r in after['routes'])


def test_unknown_cctv_state_is_not_silently_normal(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths)
    from stubs.reports import ReportStore
    store=ReportStore();report=store.create('SYNTHETIC CCTV 파손',33.25,126.561)
    store.transition(report['id'],'VERIFIED','SYNTHETIC reviewer','가상 확인')
    event=store.publish(report['id'],'SYNTHETIC-F1','cctv','normal','damaged','SYNTHETIC reviewer','가상 게시')
    with pytest.raises(ValueError):engine(request,events=[event])
    store.db.close()


def test_oversized_geometry_is_rejected_before_expensive_calculation(tmp_path,monkeypatch):
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths)
    monkeypatch.setattr('agent.data.file_engine.MAX_GEOMETRY_WORK',1)
    with pytest.raises(ValueError,match='계산 범위'):engine(request)


def test_file_engine_connects_to_conversation_api(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from agent.api import app
    route,cctv,request,paths=fixtures(tmp_path);engine=make(route,cctv,paths);agent=NightAgent(engine=engine)
    monkeypatch.setattr('agent.api.agent',agent)
    request.pop('departure')
    with TestClient(app) as client:
        response=client.post('/agent/conversation',json={'text':'2026-11-19 오후 3시','state':{'request':request,'awaiting_route':True}})
    agent.store.db.close()
    assert response.status_code==200
    result=response.json();assert result['kind']=='route' and result['synthetic'] is True
    assert result['analysis']['logic_version'].startswith('file-aeqd')
    assert all(float(r['distance'][:-1])<300 for r in result['analysis']['routes'])


def test_route_source_license_links_remain_visible(tmp_path):
    route,cctv,request,paths=fixtures(tmp_path)
    route['properties']['attribution_url']='https://example.org/license'
    route['properties']['fix_map_url']='https://example.org/fix'
    result=make(route,cctv,paths)(request)
    assert any('https://example.org/license' in x for x in result['limitations'])
    assert any('https://example.org/fix' in x for x in result['limitations'])
