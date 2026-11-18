from agent.common import check_schema, load_yaml
from agent.intent import parse
from agent.intent.methods import interpret
from agent.report.model import classify_with_model
from agent.report import classify, emergency_check, mask_personal_info
from agent.explain import explain
from stubs.engine import analyze
from stubs.reports import ReportStore,ClassificationLockedError
from agent.data_question import answer as data_answer,lookup as catalog_lookup,wants_catalog


class NightAgent:
    def __init__(self, config=None, provider=None, store=None, embedding=None, expanded_examples=None, engine=None, discovery=None):
        self.config = config or load_yaml('config/levels.yaml')['levels']['L0']
        self.provider = provider
        self.embedding=embedding
        self.expanded_examples=expanded_examples
        self.engine=engine or analyze
        self.discovery=discovery
        self.trace=[]
        self.store = store if store is not None else ReportStore()

    def route(self, request, mode='route_compare', radius=None):
        check_schema('route_request', request)
        radius=self.config.get('radius',50) if radius is None else radius
        result = self.engine(request, radius=radius, events=self.store.published_changes())
        return {'analysis': result, 'explanation': explain(result, self.provider, mode, self.config.get('explain','E1')),
                'synthetic': True}

    def report(self, text, lat=None, lng=None, user_choice=None):
        if emergency_check(text):
            return {'kind': 'emergency', 'message': load_yaml('registry/emergency_phrases.yaml')['message'],
                    'classification': classify(text), 'stored': False}
        if lat is None or lng is None:
            return {'kind': 'clarification', 'missing': ['location'], 'classification': classify(text,user_choice),
                    'message': '제보 위치를 선택해 주세요.', 'stored': False}
        result=self.store.create(text,lat,lng,user_choice)
        if self.provider is not None and self.config.get('report_llm',True):
            candidate=classify_with_model(text,user_choice,self.provider)
            # 모델 분류도 개인정보가 가려진 텍스트만 저장한다.
            try:
                result=self.store.update_classification(result['id'],candidate)
            except ClassificationLockedError:
                # 모델을 기다리는 동안 검토가 끝났다면 그 결과를 그대로 돌려준다.
                result=self.store.get(result['id'])
        return {'kind': 'report', 'report': result, 'stored': True}

    def run(self, text, context=None):
        if not isinstance(text,str):
            raise ValueError('텍스트를 입력해야 합니다.')
        if emergency_check(text):
            return self.report(text)
        if context is not None and not isinstance(context,dict):
            raise ValueError('문맥은 객체여야 합니다.')
        original_text=text
        text,_ = mask_personal_info(text)
        structure=self.config.get('structure','S1')
        self.trace=[]
        if wants_catalog(text):
            self.trace.append({'step':'catalog_lookup','local_only':True})
            return catalog_lookup(text,self.config.get('discovery',False),self.discovery)
        intent=parse(text)
        if structure not in ('S1','S2','S3'):
            raise ValueError('구조 설정 확인 필요')
        def interpret_now():
            result=interpret(text,self.config.get('intent','I1'),self.provider,self.embedding,self.expanded_examples)
            self.trace.append({'step':'interpret','method':result['method'],'fallback':result.get('fallback_reason')})
            return result
        if structure=='S1' or self.provider is None:
            intent=interpret_now()
        if structure in ('S2','S3') and self.provider is not None:
            try:
                if structure=='S3':
                    kind=self.provider.generate('kind',{'text':text})['kind']
                    self.trace.append({'step':'kind','kind':kind})
                    intent=interpret_now()
                    intent['kind']=kind
                else:
                    plan=self.provider.generate('plan',{'text':text})['tools']
                    # 스키마 외 도구·중복·순서 위반은 실행하지 않는다.
                    allowed={'parse_intent','compare_routes','classify_report','answer_data'}
                    if len(plan)!=len(set(plan)) or not set(plan)<=allowed:
                        raise ValueError('허용하지 않는 도구 계획')
                    if 'compare_routes' in plan and ('parse_intent' not in plan or plan.index('parse_intent')>plan.index('compare_routes')):
                        raise ValueError('경로 해석보다 계산이 먼저임')
                    actions=[t for t in plan if t!='parse_intent']
                    if len(actions)>1:
                        raise ValueError('한 번에 한 종류만 실행')
                    self.trace.append({'step':'tool_plan','tools':plan})
                    if 'parse_intent' in plan:
                        intent=interpret_now()
                    intent['kind']={'compare_routes':'route','classify_report':'report','answer_data':'data_question'}.get(actions[0] if actions else '', 'unsupported')
            except Exception as exc:
                self.trace.append({'step':'structure_fallback','error':type(exc).__name__})
        context = context or {}
        if context.get('request') is not None and not isinstance(context['request'],dict):
            raise ValueError('경로 문맥은 객체여야 합니다.')
        if intent['kind'] == 'report':
            # 보고서 사전 검사가 최초 저장 전에 가림 여부까지 완성한다.
            # 모델에는 classify_with_model의 가려진 요약만 전달한다.
            return self.report(original_text, context.get('lat'),context.get('lng'),context.get('user_choice'))
        if intent['kind'] in ('route', 'data_question'):
            request = {**intent['request'], **context.get('request',{})}
            missing = [k for k in ('origin','destination','departure') if k not in request]
            if missing:
                if intent['kind']=='data_question':
                    return data_answer()
                return {'kind': 'clarification','missing':missing, 'message': '출발지·도착지·출발 시각을 확인해 주세요.'}
            return {'kind': intent['kind'], **self.route(request, mode='data_question' if intent['kind']=='data_question' else 'route_compare')}
        return {'kind':'unsupported','message':'보행 경로 비교, 시설 제보, 데이터 출처 질문을 지원합니다.'}
