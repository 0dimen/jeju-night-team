import json
from copy import deepcopy
import httpx
import pytest
from agent.llm import make_provider, ProviderError, QuotaReached
from agent.intent.methods import interpret
from agent.orchestrator import NightAgent
from agent.report.model import classify_with_model
from agent.explain import explain
from stubs.engine import analyze


@pytest.mark.parametrize('structure',['S1','S2','S3'])
@pytest.mark.parametrize('method',['I1','I3','I4'])
@pytest.mark.parametrize('explanation',['E1','E2','E3'])
def test_config_swaps(structure,method,explanation):
    provider=make_provider({'provider':'mock'})
    agent=NightAgent({'structure':structure,'intent':method,'explain':explanation},provider)
    result=agent.run('제주시청에서 탑동광장까지 CCTV 2026-11-18T22:00')
    assert result['kind']=='route' and result['explanation']['validation']['passed']


def test_api_uses_header_and_post_with_cache(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','SYNTHETIC-TEST-KEY')
    calls=[]
    def handle(req):
        calls.append(req)
        assert '?' not in str(req.url)
        assert req.headers['x-goog-api-key']=='SYNTHETIC-TEST-KEY'
        body=json.loads(req.content)
        assert body['generationConfig']['responseMimeType']=='application/json'
        assert '010-1234-5678' not in req.content.decode()
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"kind":"report"}'}]}}],
                                      'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':5}})
    # 7초 대기는 실제 API와 분리한다. 네트워크 전송·캐시 계약만 검사.
    monkeypatch.setattr('agent.llm.providers.sleep',lambda _:None)
    monkeypatch.setattr('agent.llm.providers.ROOT',tmp_path)
    p=make_provider({'provider':'gemini','model':'SYNTHETIC-model','data_scope':'synthetic','cache_dir':tmp_path/'cache'},transport=httpx.MockTransport(handle))
    assert p.generate('kind',{'text':'제보 010-1234-5678'})=={'kind':'report'}
    assert p.generate('kind',{'text':'제보 010-1234-5678'})=={'kind':'report'}
    assert len(calls)==1 and p.records[-1]['cache_hit']


def test_private_data_blocked_before_network():
    p=make_provider({'provider':'gemini'},transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(AssertionError())))
    with pytest.raises(ProviderError,match='requires_synthetic'):
        p.generate('kind',{'text':'비공개 실제 제보'})


def test_gemini_cache_is_shared_across_configurations(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','SYNTHETIC-TEST-KEY')
    monkeypatch.setattr('agent.llm.providers.ROOT',tmp_path)
    calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"kind":"route"}'}]}}]})
    for name in ('first','second'):
        provider=make_provider({'provider':'gemini','model':'SYNTHETIC','data_scope':'synthetic',
            'cache_dir':tmp_path/name/'cache'},transport=httpx.MockTransport(handle))
        assert provider.generate('kind',{'text':'SYNTHETIC 같은 입력'})=={'kind':'route'}
        if name=='second':assert provider.records[-1]['cache_hit']
        provider.close()
    assert len(calls)==1


def test_gemini_same_input_concurrently_calls_once(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from time import sleep
    monkeypatch.setenv('GEMINI_API_KEY','SYNTHETIC-TEST-KEY')
    monkeypatch.setattr('agent.llm.providers.ROOT',tmp_path)
    calls=[]
    def handle(request):
        calls.append(request);sleep(.05)
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"kind":"route"}'}]}}]})
    def generate(index):
        p=make_provider({'provider':'gemini','model':'SYNTHETIC','data_scope':'synthetic'},
                        transport=httpx.MockTransport(handle))
        try:return p.generate('kind',{'text':'SYNTHETIC 동시 입력'})
        finally:p.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(generate,range(2)))==[{'kind':'route'},{'kind':'route'}]
    assert len(calls)==1


def test_quota_waits_twice_then_blocks_model(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','SYNTHETIC-TEST-KEY')
    monkeypatch.setattr('agent.llm.providers.ROOT',tmp_path)
    waits=[]; calls=[]
    monkeypatch.setattr('agent.llm.providers.sleep',waits.append)
    def handle(req):
        calls.append(req)
        return httpx.Response(429,json={'error':{'message':'SYNTHETIC test'}})
    cfg={'provider':'gemini','model':'SYNTHETIC','data_scope':'synthetic'}
    p=make_provider(cfg,transport=httpx.MockTransport(handle))
    with pytest.raises(QuotaReached): p.generate('kind',{'text':'경로'})
    assert len(calls)==3 and waits.count(60)==2
    q=make_provider(cfg,transport=httpx.MockTransport(handle))
    with pytest.raises(QuotaReached): q.generate('kind',{'text':'제보'})
    assert len(calls)==3


def test_malformed_model_json_falls_back():
    class Bad:
        def generate(self,*args): raise json.JSONDecodeError('invalid','{',1)
    result=interpret('가로등이 있는 경로',method='I3',provider=Bad())
    assert result['fallback_reason']=='JSONDecodeError'


def test_model_cannot_invent_locations_or_time():
    class Invent:
        def generate(self,*a):
            return {'kind':'route','preferences':['streetlight'],'origin_name':'제주공항',
                    'destination_name':'탑동광장','departure':'2030-01-01T22:00'}
    result=interpret('제주시청에서 탑동광장까지',method='I3',provider=Invent())
    assert 'origin' not in result['request'] and 'departure' not in result['request']


def test_plan_cannot_publish_or_approve():
    class Evil:
        def generate(self,task,payload): return {'tools':['approve_report','publish']}
    agent=NightAgent({'structure':'S2','intent':'I1','explain':'E1'},Evil())
    result=agent.run('제주시청에서 탑동광장까지 2026-11-18T22:00')
    assert result['kind']=='route'
    assert agent.trace[-1]['step']=='structure_fallback'
    assert agent.store.published_changes()==[]


def test_reordered_plan_falls_back():
    class BadPlan:
        def generate(self,*a): return {'tools':['compare_routes','parse_intent']}
    agent=NightAgent({'structure':'S2','intent':'I1','explain':'E1'},BadPlan())
    assert agent.run('제주시청에서 탑동광장까지 2026-11-18T22:00')['kind']=='route'
    assert agent.trace[-1]['step']=='structure_fallback'


def test_tool_plan_precedes_selected_interpretation():
    class Recording:
        def __init__(self):
            self.tasks=[]; self.mock=make_provider({'provider':'mock'})
        def generate(self,task,payload):
            self.tasks.append(task)
            return self.mock.generate(task,payload)
    p=Recording()
    agent=NightAgent({'structure':'S2','intent':'I3','explain':'E1'},p)
    assert agent.run('제주시청에서 탑동광장까지 CCTV 2026-11-18T22:00')['kind']=='route'
    assert p.tasks==['plan','intent']


def test_hybrid_only_requests_connector(request_data):
    class Recording:
        def __init__(self): self.tasks=[]
        def generate(self,task,payload):
            self.tasks.append(task)
            return {'connector':'자료 기준일과 한계를 함께 확인하세요.'}
    p=Recording(); output=explain(analyze(request_data),p,method='E3')
    assert output['generated_by']=='hybrid' and p.tasks==['connect']


def test_model_cannot_remove_masking_or_emergency():
    class Evil:
        def generate(self,*a):
            return {'facility':'streetlight','problem':'not_working','summary':'새 원문 010-1111-2222',
                    'confidence':1.,'conflict_with_user_choice':False,'personal_info_masked':False,'emergency':False}
    result=classify_with_model('가로등 꺼짐 010-1234-5678',provider=Evil())
    assert result['personal_info_masked'] and '010' not in result['summary']


def test_route_bad_output_retries_once_then_template(request_data):
    class Bad:
        calls=0
        def generate(self,task,payload):
            self.calls+=1
            result=deepcopy(payload['template']); result['tradeoff']='무료로 999m 이동'
            return result
    p=Bad(); output=explain(analyze(request_data),p,method='E2')
    assert p.calls==2 and output['generated_by']=='template'
    assert '999' not in output['tradeoff']


def test_missing_paid_keys_safe(monkeypatch):
    for name,key in [('anthropic','ANTHROPIC_API_KEY'),('openai','OPENAI_API_KEY')]:
        monkeypatch.delenv(key,raising=False)
        p=make_provider({'provider':name,'model':'SYNTHETIC'})
        with pytest.raises(ProviderError,match='key_unavailable'):
            p.generate('kind',{'text':'경로'})


def test_mask_metadata_survives_agent_and_storage():
    a=NightAgent({'structure':'S1','intent':'I3','explain':'E2'},make_provider({'provider':'mock'}))
    result=a.run('가로등 꺼짐 010-1234-5678',{'lat':33.5,'lng':126.5})
    assert result['report']['classification']['personal_info_masked']
    assert a.store.get(result['report']['id'])['classification']['personal_info_masked']
