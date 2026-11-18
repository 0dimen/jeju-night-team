import re
from agent.common import load_yaml
from agent.intent import parse, PLACES


def interpret(text,method='I1',provider=None,embedding=None,expanded_examples=None):
    baseline=parse(text)
    if method=='I1':
        return baseline
    if method=='I2':
        if embedding is None:
            baseline['fallback_reason']='embedding_unavailable'
            return baseline
        result=embedding.classify(text)
        baseline['request']['preferences']=result['preferences'] or ['none']
        baseline['method']='embedding'
        baseline['scores']=result['scores']
        return baseline
    if method not in ('I3','I4'):
        raise ValueError('입력 해석 방식 확인 필요')
    if provider is None:
        baseline['fallback_reason']='provider_unavailable'
        return baseline
    try:
        payload={'text':text,'known_places':list(PLACES),
                 'enum_definitions':{'kind':{'route':'보행 경로 비교','report':'시설 고장·상태 제보',
                    'data_question':'출처·기간·통계 질문','unsupported':'지원 범위 밖'},
                    'preferences':{'cctv':'CCTV 인접 구간 참고','streetlight':'가로등·조명 참고',
                                   'activity':'지역 활동 통계 참고','none':'선호 없음'}},
                 'enum_examples':load_yaml('registry/enums.yaml')['preferences']}
        if method=='I4':
            # 승인된 표현만 운영 사전에 반영한다. 실험 후보는 별도 입력으로만 제공.
            payload['expanded_candidate_examples']=expanded_examples or {}
            payload['candidate_only']=True
        output=provider.generate('intent',payload)
        request={'preferences':output['preferences'] or ['none']}
        if len(request['preferences'])>1 and 'none' in request['preferences']:
            request['preferences'].remove('none')
        for field in ('origin','destination'):
            name=output[field+'_name']
            if name and name in text and name in PLACES:
                lat,lng=PLACES[name]
                request[field]={'name':name,'lat':lat,'lng':lng}
        departure=output['departure']
        if departure and departure in text and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',departure):
            request['departure']=departure
        missing=[f for f in ('origin','destination','departure') if f not in request] if output['kind']=='route' else []
        return {'kind':output['kind'],'request':request,'uncertain_fields':missing,'method':method}
    except Exception as exc:
        baseline['fallback_reason']=type(exc).__name__
        return baseline
