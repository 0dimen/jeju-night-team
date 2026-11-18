from contextlib import nullcontext
import json
import httpx
import pytest
from agent.llm import make_provider,ProviderError


def test_local_repeats_use_fixed_seed_but_separate_cache_entries(tmp_path,monkeypatch):
    monkeypatch.setattr('agent.llm.providers.model_lock',nullcontext)
    seeds=[]
    def handle(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[]})
        body=json.loads(request.content)
        seeds.append(body['options']['seed'])
        assert body['keep_alive']==0 and 'JSON Schema' in body['messages'][0]['content']
        return httpx.Response(200,json={'message':{'content':'{"kind":"route"}'}})
    provider=make_provider({'provider':'ollama','model':'SYNTHETIC','data_scope':'synthetic','cache_dir':tmp_path},transport=httpx.MockTransport(handle))
    provider.generate('kind',{'text':'경로'})
    provider.repeat=1
    provider.generate('kind',{'text':'경로'})
    assert seeds==[42,42]


def test_error_code_is_kept_without_provider_body_or_key(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','SYNTHETIC-SECRET-MUST-NOT-LOG')
    monkeypatch.setattr('agent.llm.providers.gemini_rate_lock',nullcontext)
    monkeypatch.setattr('agent.llm.providers.ROOT',tmp_path)
    provider=make_provider({'provider':'gemini','model':'SYNTHETIC','data_scope':'synthetic'},
        transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'error':{'message':'SYNTHETIC-SECRET-MUST-NOT-LOG'}})))
    with pytest.raises(ProviderError):provider.generate('kind',{'text':'경로'})
    assert provider.records[-1]['error_code']=='http_status_400'
    assert 'MUST-NOT-LOG' not in json.dumps(provider.records)
