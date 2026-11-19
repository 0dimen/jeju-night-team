"""합성 위치·응답으로 페이지 한정 비저장과 계산을 확인. 실제 개인 주소는 사용하지 않는다."""
import json,math
import httpx
import pytest
from fastapi.testclient import TestClient
from agent.api import app,agent
from agent.data import tmap_routes as t
from agent.data import selected_routes as selected
from agent.geometry import indexed_covered_length,covered_length


@pytest.fixture
def fixture(monkeypatch,tmp_path):
    monkeypatch.setenv('TMAP_APP_KEY','test-only-not-a-real-key');monkeypatch.setenv('TMAP_PUBLIC_CACHE_DIR',str(tmp_path))
    monkeypatch.setattr(t,'_last_call',0);monkeypatch.setattr(t,'_blocked_until',0)
    monkeypatch.setattr(t.time,'sleep',lambda n:None)
    meta={'name':'SYNTHETIC','source_rows':1,'selected_rows':1,'purpose_rows':{},'purposes':['생활방범'],'basis_dates':{'SYNTHETIC':1}}
    monkeypatch.setattr(selected,'load_facilities',lambda source:([(126.49,33.49)],[(126.491,33.49)],{'SYNTHETIC':{'basis_date':'SYNTHETIC','source_rows':1}},meta))
    cls=httpx.Client;calls=[]
    def handler(request):
        assert request.method=='POST' and request.url.query==b'version=1'
        body=json.loads(request.content);assert body['startName']=='start' and body['endName']=='end'
        calls.append(body)
        return httpx.Response(200,json={'type':'FeatureCollection','features':[{'properties':{'totalDistance':93,'totalTime':80},'geometry':{'type':'LineString','coordinates':[[126.49,33.49],[126.491,33.49]]}}]})
    c=TestClient(app)
    monkeypatch.setattr(t.httpx,'Client',lambda **kw:cls(transport=httpx.MockTransport(handler),**kw))
    return c,calls,tmp_path


def request():return {'origin':{'lat':33.49,'lng':126.49,'name':'SYNTHETIC 집'},'destination':{'lat':33.49,'lng':126.491},'departure':'2026-11-20T21:00'}


def test_private_route_never_writes_cache_or_report(fixture):
    c,calls,folder=fixture;before=agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    response=c.post('/research/routes/selected',json=request())
    assert response.status_code==200,response.text
    data=response.json();assert data['private_request'] and not data['page_location_stored'] and not data['stored']
    assert data['region']=='custom' and len(data['routes'])==1 and data['map_points']['points']
    assert 'SYNTHETIC 집' not in response.text and 'state' not in data
    assert response.headers['Cache-Control']=='no-store' and not list(folder.iterdir())
    assert agent.store.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0]==before
    assert len(calls)==3


def test_ambiguous_date_and_far_points_rejected_before_provider(fixture):
    c,calls,_=fixture
    for bad in ('2026-11-20','2026-11-20T25:00','2026-02-30T21:00'):
        data=request();data['departure']=bad;assert c.post('/research/routes/selected',json=data).status_code==422
    data=request();data['destination']={'lat':33.49,'lng':127.49}
    assert c.post('/research/routes/selected',json=data).status_code==422
    assert not calls


def test_spatial_index_preserves_union_length():
    points=[(0.,0.),(100.,0.),(100.,50.)]
    facilities=[{'x':20.,'y':0.},{'x':25.,'y':0.},{'x':100.,'y':25.},{'x':9999.,'y':9999.}]
    assert indexed_covered_length(points,facilities,10)==pytest.approx((45.,150.))
    assert indexed_covered_length(points,facilities,10)==pytest.approx(covered_length(points,facilities,10))


def test_private_tile_coordinates_use_post(monkeypatch):
    from agent.maps import vworld
    calls=[]
    monkeypatch.setattr(vworld,'fetch_tile',lambda z,x,y:calls.append((z,x,y)) or b'PNG-SYNTHETIC')
    response=TestClient(app).post('/maps/vworld/tile',json={'z':17,'x':111589,'y':52582})
    assert response.status_code==200 and calls==[(17,111589,52582)]
