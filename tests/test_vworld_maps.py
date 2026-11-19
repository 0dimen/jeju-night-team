"""키 비노출·타일 범위·제공사 실패 격리. 응답 영상은 공개 타일 형식의 시험 대역."""
import base64
import httpx
import pytest
from fastapi.testclient import TestClient
from agent.api import app
from agent.maps import vworld
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=')

@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(vworld,'_blocked_until',0)
    vworld._requests.clear()
    monkeypatch.delenv('VWORLD_API_KEY',raising=False)
    monkeypatch.delenv('VWORLD_DOMAIN',raising=False)


def test_missing_key_and_scope_do_not_call_provider(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('외부 요청 금지')
    monkeypatch.setattr(httpx,'Client',forbidden)
    c=TestClient(app)
    assert c.get('/maps/vworld/status').json()['configured'] is False
    assert c.get('/maps/vworld/tiles/17/111589/52582.png').status_code==503
    assert c.get('/maps/vworld/tiles/17/1/1.png').status_code==422
    assert c.get('/maps/vworld/tiles/25/1/1.png').status_code==422


def provider(monkeypatch,status,body):
    cls=httpx.Client
    monkeypatch.setenv('VWORLD_API_KEY','test-only-not-a-real-key')
    def handler(request):
        assert request.url.host=='api.vworld.kr'
        assert '/test-only-not-a-real-key/' in request.url.path
        return httpx.Response(status,content=body)
    monkeypatch.setattr(vworld.httpx,'Client',lambda **kwargs:cls(transport=httpx.MockTransport(handler),**kwargs))


def test_png_response_and_no_key_in_status(monkeypatch):
    c=TestClient(app);provider(monkeypatch,200,PNG)
    r=c.get('/maps/vworld/tiles/17/111589/52582.png')
    assert r.status_code==200 and r.content==PNG
    assert r.headers['cache-control']=='no-store'
    status=c.get('/maps/vworld/status');assert status.json()['configured']
    assert 'test-only-not-a-real-key' not in status.text


@pytest.mark.parametrize('status,body',[(403,b'test-only-not-a-real-key'),(429,b'quota'),(200,b'<xml>test-only-not-a-real-key</xml>')])
def test_provider_errors_do_not_expose_body_or_key(monkeypatch,status,body):
    c=TestClient(app);provider(monkeypatch,status,body)
    r=c.get('/maps/vworld/tiles/17/111589/52582.png')
    assert r.status_code==503
    assert 'test-only-not-a-real-key' not in r.text and '<xml>' not in r.text


def test_quota_backoff_no_second_external_call(monkeypatch):
    c=TestClient(app);provider(monkeypatch,429,b'quota')
    assert c.get('/maps/vworld/tiles/17/111589/52582.png').status_code==503
    def forbidden(**kw):raise AssertionError('재호출 금지')
    monkeypatch.setattr(vworld.httpx,'Client',forbidden)
    assert c.get('/maps/vworld/tiles/17/111589/52582.png').status_code==503


def test_http_log_redacts_server_key(monkeypatch,caplog):
    import logging
    monkeypatch.setenv('VWORLD_API_KEY','test-only-not-a-real-key')
    with caplog.at_level(logging.INFO,logger='httpx'):
        logging.getLogger('httpx').info('GET https://api.vworld.kr/req/wmts/1.0.0/%s/Base/17/52582/111589.png','test-only-not-a-real-key')
    assert 'test-only-not-a-real-key' not in caplog.text
    assert '[REDACTED]' in caplog.text
