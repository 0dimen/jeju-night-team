"""합성 검색 응답 대역으로 POST·키 비노출·선택 후보·무저장을 검사."""
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from agent.api import app
from agent.maps.search import search_places

def test_search_uses_post_body_and_returns_candidates(monkeypatch):
    key='test-only-not-a-real-key';monkeypatch.setenv('VWORLD_API_KEY',key)
    cls=httpx.Client;c=TestClient(app)
    def handler(request):
        assert request.method=='POST' and not request.url.query
        assert key not in str(request.url)
        assert b'query=' in request.content
        return httpx.Response(200,json={'response':{'status':'OK','result':{'items':[
            {'title':'SYNTHETIC 공원','point':{'x':'126.49','y':'33.49'},'address':{'road':'SYNTHETIC 주소'}},
            {'title':'SYNTHETIC 다른 지역','point':{'x':'127','y':'37'},'address':{}}]}}})
    monkeypatch.setattr('agent.maps.search.httpx.Client',lambda **kw:cls(transport=httpx.MockTransport(handler),**kw))
    r=c.post('/maps/places/search',json={'query':'SYNTHETIC 장소'})
    assert r.status_code==200 and r.headers['Cache-Control']=='no-store'
    assert len(r.json()['candidates'])==1 and not r.json()['stored'] and key not in r.text
    assert 'state' not in r.json()


def test_failed_search_no_echo_of_query_or_key(monkeypatch):
    cls=httpx.Client;c=TestClient(app);monkeypatch.setenv('VWORLD_API_KEY','test-only-not-a-real-key')
    monkeypatch.setattr('agent.maps.search.httpx.Client',lambda **kw:cls(transport=httpx.MockTransport(lambda r:httpx.Response(403,text='test-only-not-a-real-key')),**kw))
    response=c.post('/maps/places/search',json={'query':'SYNTHETIC 개인 주소'})
    assert response.status_code==503 and '개인 주소' not in response.text and 'test-only' not in response.text


def test_no_key_and_invalid_input(monkeypatch):
    monkeypatch.delenv('VWORLD_API_KEY',raising=False)
    c=TestClient(app)
    assert c.post('/maps/places/search',json={'query':'공원'}).status_code==503
    assert c.post('/maps/places/search',json={'query':'x'*121}).status_code==422
