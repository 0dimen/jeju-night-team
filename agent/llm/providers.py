"""모든 공급자는 generate(task, payload)로 스키마에 맞는 객체를 반환한다."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep, time
import json
import os
import re
import threading

import httpx
import jsonschema
from agent.file_lock import process_lock
from agent.common import ROOT, stable_hash
from agent.intent import parse
from agent.report import classify, mask_personal_info
from .schemas import schema_for, system_prompt


class ProviderError(RuntimeError):
    pass


class QuotaReached(ProviderError):
    pass


def safe_payload(value):
    if isinstance(value,str):
        return mask_personal_info(value)[0]
    if isinstance(value,dict):
        return {k:safe_payload(v) for k,v in value.items()}
    if isinstance(value,list):
        return [safe_payload(v) for v in value]
    return value


class Provider:
    def __init__(self,name,model='',cache_dir=None,timeout=90,transport=None,data_scope='private',repeat=0,deadline=None):
        self.name,self.model,self.timeout,self.data_scope=name,model,timeout,data_scope
        self.cache_dir=Path(cache_dir) if cache_dir else None
        if name=='gemini' and data_scope in ('synthetic','public'):
            self.cache_dir=ROOT/'experiments/results/gemini_shared/cache'
        self.repeat=repeat
        self.deadline=deadline
        self.client=httpx.Client(timeout=timeout,transport=transport)
        self.records=[]
        self.quota_failed=False

    def close(self):
        self.client.close()

    def remaining(self):
        remaining=self.deadline-time() if self.deadline is not None else self.timeout
        if remaining<=0:
            raise TimeoutError('report_deadline')
        return min(self.timeout,remaining)

    def wait(self,seconds):
        if self.deadline is not None and time()+seconds>=self.deadline:
            raise TimeoutError('report_deadline')
        sleep(seconds)

    def generate(self,task,payload):
        if self.name=='gemini' and self.data_scope not in ('synthetic','public'):
            raise ProviderError('free_api_requires_synthetic_or_public_data')
        payload=safe_payload(payload)
        schema=schema_for(task)
        key=stable_hash({'provider':self.name,'model':self.model,'task':task,'payload':payload,
                         'schema':schema,'prompt':system_prompt(task),'repeat':self.repeat})
        if self.name=='gemini':
            with cache_entry_lock(key):
                return self._cached_generate(task,payload,schema,key)
        return self._cached_generate(task,payload,schema,key)

    def _cached_generate(self,task,payload,schema,key):
        cache=self.cache_dir/f'{key}.json' if self.cache_dir and self.data_scope in ('synthetic','public') else None
        if self.name=='gemini' and cache and not cache.exists():
            # 앞선 조합별 캐시도 가장 이른 응답부터 재사용한다. 원시 결과는 보존한다.
            legacy=sorted((ROOT/'experiments/results').glob('*/cache/'+key+'.json'),key=lambda p:p.stat().st_mtime)
            for path in legacy:
                if path==cache:continue
                data=json.loads(path.read_text(encoding='utf-8'))
                if data.get('record',{}).get('provider')!='gemini':continue
                jsonschema.Draft202012Validator(schema).validate(data['output'])
                cache.parent.mkdir(parents=True,exist_ok=True)
                cache.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                break
        if cache and cache.exists():
            data=json.loads(cache.read_text(encoding='utf-8'))
            jsonschema.Draft202012Validator(schema).validate(data['output'])
            self.records.append({**data['record'],'cache_hit':True,'elapsed_seconds':0.})
            return data['output']
        start=monotonic()
        try:
            output,meta=self._generate(task,payload,schema)
            if isinstance(output,str):
                output=json.loads(output)
            jsonschema.Draft202012Validator(schema).validate(output)
        except Exception as exc:
            record={'task':task,'cache_hit':False,'elapsed_seconds':monotonic()-start,'error':type(exc).__name__}
            if isinstance(exc,ProviderError) and re.fullmatch(r'http_status_\d{3}',str(exc)):
                record['error_code']=str(exc)
            self.records.append(record)
            raise
        record={'provider':self.name,'model':self.model,'task':task,'cache_hit':False,
                'elapsed_seconds':monotonic()-start,**meta}
        self.records.append(record)
        if cache:
            cache.parent.mkdir(parents=True,exist_ok=True)
            tmp=cache.with_suffix('.tmp')
            tmp.write_text(json.dumps({'output':output,'record':record},ensure_ascii=False),encoding='utf-8')
            tmp.replace(cache)
        return output

    def _post(self,url,body,headers=None):
        # 전체 오류 응답·URL·헤더를 예외에 넣지 않는다.
        try:
            response=self.client.post(url,json=body,headers=headers,timeout=self.remaining())
        except httpx.TimeoutException as exc:
            raise TimeoutError('provider_timeout') from None
        if response.status_code>=400:
            raise ProviderError('http_status_'+str(response.status_code))
        return response.json()

    def _generate(self,task,payload,schema):
        if self.name=='none':
            raise ProviderError('provider_disabled')
        if self.name=='mock':
            if payload.get('force_error'):
                raise TimeoutError('SYNTHETIC timeout')
            if task=='connect':
                from agent.explain.connectors import CONNECTORS
                output={'connector':CONNECTORS[0]}
            elif task=='explain':
                output=deepcopy(payload['template'])
            elif task=='report':
                output=classify(payload['text'],payload.get('user_choice'))
            else:
                parsed=parse(payload['text'])
                if task=='kind':
                    output={'kind':parsed['kind']}
                elif task=='plan':
                    output={'tools': {'route':['parse_intent','compare_routes'],'report':['classify_report'],'data_question':['answer_data']}.get(parsed['kind'],[])}
                else:
                    request=parsed['request']
                    output={'kind':parsed['kind'],'preferences':request['preferences'],
                            'origin_name':request.get('origin',{}).get('name'),'destination_name':request.get('destination',{}).get('name'),
                            'departure':request.get('departure')}
            return output,{'input_tokens':0,'output_tokens':0,'synthetic_mock':True}
        prompt=system_prompt(task)+'\n출력 JSON Schema:\n'+json.dumps(strip_schema(schema),ensure_ascii=False)+'\n입력 데이터:\n'+json.dumps(payload,ensure_ascii=False)
        if self.name=='ollama':
            with model_lock():
                loaded=self.client.get('http://127.0.0.1:11434/api/ps',timeout=self.remaining()).json().get('models',[])
                if any(m['name']!=self.model for m in loaded):
                    raise ProviderError('another_local_model_is_loaded')
                response=self._post('http://127.0.0.1:11434/api/chat',
                    {'model':self.model,'stream':False,'think':False,'keep_alive':0,
                     'options':{'temperature':0,'seed':42,'num_ctx':4096,
                                'num_predict':1400 if task=='explain' else 450,'num_thread':2},
                     'format':strip_schema(schema),'messages':[{'role':'user','content':prompt}]})
                return response['message']['content'],{'input_tokens':response.get('prompt_eval_count'),
                    'output_tokens':response.get('eval_count'),'eval_seconds':response.get('eval_duration',0)/1e9,
                    'load_seconds':response.get('load_duration',0)/1e9}
        if self.name=='gemini':
            return self._gemini(prompt,schema)
        keyname={'anthropic':'ANTHROPIC_API_KEY','openai':'OPENAI_API_KEY'}[self.name]
        key=os.environ.get(keyname)
        if not key:
            raise ProviderError('key_unavailable:'+keyname)
        if self.name=='openai':
            response=self._post('https://api.openai.com/v1/chat/completions',
                {'model':self.model,'messages':[{'role':'user','content':prompt}],
                 'response_format':{'type':'json_schema','json_schema':{'name':task,'strict':True,'schema':strip_schema(schema)}}},
                {'Authorization':'Bearer '+key})
            return response['choices'][0]['message']['content'],response.get('usage',{})
        response=self._post('https://api.anthropic.com/v1/messages',
            {'model':self.model,'max_tokens':1800,'messages':[{'role':'user','content':prompt}],
             'tools':[{'name':'structured_result','description':'Return structured result','input_schema':strip_schema(schema)}],
             'tool_choice':{'type':'tool','name':'structured_result'}},
            {'x-api-key':key,'anthropic-version':'2023-06-01'})
        output=next(x['input'] for x in response['content'] if x['type']=='tool_use')
        return output,response.get('usage',{})

    def _gemini(self,prompt,schema):
        key=os.environ.get('GEMINI_API_KEY')
        if not key:
            raise ProviderError('key_unavailable:GEMINI_API_KEY')
        if self.quota_failed:
            raise QuotaReached('무료 한도 도달')
        quota_path=ROOT/'experiments/results'/('gemini_quota_'+stable_hash(self.model)+'.json')
        if quota_path.exists():
            raise QuotaReached('무료 한도 도달')
        body={'contents':[{'role':'user','parts':[{'text':prompt}]}],
              'generationConfig':{'temperature':0,'maxOutputTokens':2400,
                                  'responseMimeType':'application/json','responseJsonSchema':strip_schema(schema)}}
        if '2.5-flash' in self.model:
            body['generationConfig']['thinkingConfig']={'thinkingBudget':0}
        quota_count=0
        while True:
            # 프로세스가 재시작돼도 마지막 실제 호출부터 최소 7초를 지킨다.
            with gemini_rate_lock():
                rate=ROOT/'experiments/results/gemini_rate.json'
                previous=json.loads(rate.read_text(encoding='utf-8')).get('last_call',0) if rate.exists() else 0
                wait=max(0.,7-(time()-previous))
                if wait:
                    self.wait(wait)
                rate.parent.mkdir(parents=True,exist_ok=True)
                rate.write_text(json.dumps({'last_call':time()}),encoding='utf-8')
                response=self.client.post('https://generativelanguage.googleapis.com/v1beta/models/'+self.model+':generateContent',
                                          json=body,headers={'x-goog-api-key':key},timeout=self.remaining())
            if response.status_code==429:
                quota_count+=1
                if quota_count>=3:
                    self.quota_failed=True
                    quota_path.parent.mkdir(parents=True,exist_ok=True)
                    quota_path.write_text(json.dumps({'model':self.model,'failures':3,'at':time(),
                                                       'status':'무료 한도 도달'},ensure_ascii=False),encoding='utf-8')
                    raise QuotaReached('무료 한도 도달')
                self.wait(60)
                continue
            if response.status_code>=400:
                raise ProviderError('http_status_'+str(response.status_code))
            data=response.json()
            parts=data['candidates'][0]['content']['parts']
            text=''.join(p.get('text','') for p in parts if not p.get('thought'))
            usage=data.get('usageMetadata',{})
            return text,{'input_tokens':usage.get('promptTokenCount'),
                         'output_tokens':usage.get('candidatesTokenCount'),
                         'thinking_tokens':usage.get('thoughtsTokenCount',0),'quota_retries':quota_count,
                         'actual_model':data.get('modelVersion',self.model)}


def strip_schema(schema):
    if isinstance(schema,dict):
        return {k:strip_schema(v) for k,v in schema.items() if k not in ('$schema','$id')}
    if isinstance(schema,list):
        return [strip_schema(v) for v in schema]
    return schema


def cache_entry_lock(key):
    return process_lock('jeju-night-gemini-cache-'+key+'.lock')


def model_lock():
    return process_lock('jeju-night-ollama.lock')


def gemini_rate_lock():
    return process_lock('jeju-night-gemini.lock')


def make_provider(config=None,**kwargs):
    config=config or {}
    name=config.get('provider','none')
    if name not in ('none','mock','ollama','gemini','openai','anthropic'):
        raise ValueError('지원하지 않는 공급자')
    return Provider(name,model=config.get('model',''),data_scope=config.get('data_scope','private'),
                    cache_dir=config.get('cache_dir'),timeout=config.get('timeout',90),
                    repeat=config.get('repeat',0),deadline=config.get('deadline'),**kwargs)
