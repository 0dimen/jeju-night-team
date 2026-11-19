"""보행 제공사 연결·입력 보존·오류 격리. 합성 GeoJSON은 명시적 시험 대역."""
from types import SimpleNamespace
from pathlib import Path
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from agent.api import app
from agent.data import tmap_routes as t


def router():
    graph={'center':(126.49,33.49),'scale':(93000,110540),'nodes':{1:{'xy':(-1000,-1000)},2:{'xy':(1000,1000)}}}
    return SimpleNamespace(start=(126.49,33.49),goal=(126.491,33.49),graph=graph,lights=[(126.49,33.49)],cctv=[(126.491,33.49)],region='yeondong',label='SYNTHETIC 공개 구간 대역',sources={'cctv':{'name':'SYNTHETIC'},'light':{'name':'SYNTHETIC'}})

def synthetic_geo():
    return {'type':'FeatureCollection','features':[{'properties':{'totalDistance':93,'totalTime':80},'geometry':{'type':'LineString','coordinates':[[126.49,33.49],[126.491,33.49]]}}]}

@pytest.fixture(autouse=True)
def fresh(monkeypatch,tmp_path):
    monkeypatch.setenv('TMAP_PUBLIC_CACHE_DIR',str(tmp_path));monkeypatch.setenv('TMAP_APP_KEY','test-only-not-a-real-key')
    monkeypatch.setattr(t,'_blocked_until',0);monkeypatch.setattr(t,'_last_call',0)

def test_endpoint_and_geometry_validation():
    with pytest.raises(ValueError):t.normalized({'type':'FeatureCollection','features':['invalid']},router(),'10')
    r=router();good=t.normalized(synthetic_geo(),r,'10');assert good['provider_distance_m']==93
    bad=synthetic_geo();bad['features'].append({'geometry':{'type':'LineString','coordinates':[[126.492,33.49],[126.493,33.49]]}})
    with pytest.raises(ValueError,match='끊어진'):t.normalized(bad,r,'10')
    bad=synthetic_geo();bad['features'][0]['properties']['totalDistance']=9999
    with pytest.raises(ValueError,match='차이'):t.normalized(bad,r,'10')
    bad=synthetic_geo();bad['features'][0]['geometry']['coordinates'][0]=[127.4,33.49]
    with pytest.raises(ValueError):t.normalized(bad,r,'10')

def test_post_header_no_names_or_key_in_cache(monkeypatch):
    cls=httpx.Client;calls=[]
    def handler(request):
        calls.append(request)
        assert request.headers['appKey']=='test-only-not-a-real-key'
        assert 'test-only' not in str(request.url)
        body=json.loads(request.content);assert body['startName']=='start' and body['endName']=='end'
        assert 'startX' not in str(request.url)
        return httpx.Response(200,json=synthetic_geo())
    monkeypatch.setattr(t.httpx,'Client',lambda **kw:cls(transport=httpx.MockTransport(handler),**kw))
    first=t.fetch_route(router(),'10');second=t.fetch_route(router(),'10')
    assert not first['cached'] and second['cached'] and len(calls)==1
    assert 'test-only-not-a-real-key' not in t.cache_path(router(),'10').read_text()

def test_duplicate_options_keep_one_route_and_all_estimates(monkeypatch):
    def candidate(r,option):return {**t.normalized(synthetic_geo(),r,option),'cached':True,'fetched_at':'2026-11-19T00:00:00+00:00'}
    monkeypatch.setattr(t,'fetch_route',candidate)
    view=t.compare(router());assert len(view['routes'])==1 and view['same_route']
    assert view['routes'][0]['options']==['10','4','30']
    assert len(view['routes'][0]['option_summaries'])==3
    assert view['routes'][0]['walk_review']['reviewed_segments']==0

def test_all_fail_no_synthetic_substitution(monkeypatch):
    def forbidden(*args):raise t.TmapUnavailable('test-only-not-a-real-key')
    monkeypatch.setattr(t,'fetch_route',forbidden)
    monkeypatch.setattr('agent.data.research_router.get_router',lambda *a:router())
    r=TestClient(app).post('/research/routes/tmap',json={'region':'yeondong'})
    assert r.status_code==503 and 'test-only' not in r.text

def test_outside_compiled_coverage_is_unavailable():
    with pytest.raises(ValueError,match='범위 밖'):t.coverage(router(),[[126.52,33.49],[126.53,33.49]],50,'cctv')

def test_429_stops_next_request(monkeypatch):
    cls=httpx.Client;calls=[]
    def handler(request):calls.append(1);return httpx.Response(429,json={'message':'test-only-not-a-real-key'})
    monkeypatch.setattr(t.httpx,'Client',lambda **kw:cls(transport=httpx.MockTransport(handler),**kw))
    for _ in range(2):
        with pytest.raises(t.TmapUnavailable):t.fetch_route(router(),'10')
    assert len(calls)==1

def test_invalid_region_does_not_call_provider(monkeypatch):
    def forbidden(*args):raise AssertionError('요청 금지')
    monkeypatch.setattr(t,'fetch_route',forbidden)
    assert TestClient(app).post('/research/routes/tmap',json={'region':'home'}).status_code==422
