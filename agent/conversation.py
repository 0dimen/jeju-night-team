"""페이지 메모리 상태를 주고받는 대화 처리. 서버 세션·집 위치 저장소는 없다."""
from copy import deepcopy
from datetime import date,datetime
import math
import re
from agent.common import load_yaml,check_schema
from agent.intent import parse
from agent.report import emergency_check


def page_turn(text,state=None):
    if emergency_check(text):
        return {'kind':'emergency','message':load_yaml('registry/emergency_phrases.yaml')['message'],
                'state':{},'stored':False}
    if not isinstance(state,(dict,type(None))):raise ValueError('페이지 상태 형식 확인')
    source=state or {}
    # 알 수 없는 상태·이전 대화 원문은 되돌려 주지 않는다.
    current={k:deepcopy(source[k]) for k in ('request','date','hour','minute','period','awaiting_route') if k in source}
    request=current.setdefault('request',{})
    if not isinstance(request,dict):raise ValueError('경로 상태 형식 확인')
    request={k:v for k,v in request.items() if k in ('origin','destination','preferences','departure')}
    current['request']=request
    for field in ('origin','destination'):
        if field in request:
            p=request[field]
            if not isinstance(p,dict) or not isinstance(p.get('name'),str):raise ValueError('위치 이름 확인')
            if any(isinstance(p.get(k),bool) or not isinstance(p.get(k),(int,float)) or not math.isfinite(p[k]) for k in ('lat','lng')):raise ValueError('위치 좌표 확인')
            if not(-90<=p['lat']<=90 and -180<=p['lng']<=180):raise ValueError('위치 범위 확인')
            request[field]={k:p[k] for k in ('name','lat','lng')}
    intent=parse(text)
    # 출처 질문·제보·긴급은 경로 시각 확인 대화에 묶지 않는다.
    if intent['kind'] in ('data_question','report'):
        return {'kind':'delegate','text':text,'state':{},'stored':False}
    route=intent['kind']=='route' or bool(re.search(r'집으로|초등학교|대학교',text)) or current.get('awaiting_route') is True
    if not route:return {'kind':'delegate','text':text,'state':{},'stored':False}
    current['awaiting_route']=True
    for field in ('origin','destination'):
        if field in intent['request']:request[field]=intent['request'][field]
    request.setdefault('preferences',intent['request'].get('preferences',['none']))
    # 날짜·오전·오후를 현재 시각으로 추정하지 않는다.
    found=re.search(r'(\d{4}-\d{2}-\d{2})(?:T(\d{2}):(\d{2}))?',text)
    if found:
        date.fromisoformat(found[1]);current['date']=found[1]
        if found[2] is not None:
            h,m=int(found[2]),int(found[3])
            if not(0<=h<24 and 0<=m<60):raise ValueError('시각 범위 확인')
            current.update(hour=h,minute=m,period='24h')
    if not (found and found[2] is not None):
        found_hour=re.search(r'(?<!\d)(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?',text)
        if found_hour:
            h,m=int(found_hour[1]),int(found_hour[2] or 0)
            if not(0<=h<24 and 0<=m<60):raise ValueError('시각 범위 확인')
            current.update(hour=h,minute=m)
            current.pop('period',None)
            if h>12 or h==0:current['period']='24h'
    if found or re.search(r'(?<!\d)\d{1,2}\s*시',text) or '오전' in text or '오후' in text:
        request.pop('departure',None)
    if '오전' in text:current['period']='am'
    elif '오후' in text:current['period']='pm'
    if 'date' in current:date.fromisoformat(current['date'])
    if 'hour' in current:
        h=current['hour'];m=current.get('minute',0)
        if isinstance(h,bool) or not isinstance(h,int) or not 0<=h<24 or isinstance(m,bool) or not isinstance(m,int) or not 0<=m<60:raise ValueError('시각 상태 확인')
        if current.get('period') in ('am','pm') and not 1<=h<=12:raise ValueError('오전·오후 시각은 1~12시 확인')
    if 'departure' in request:
        datetime.fromisoformat(request['departure'])
    elif all(k in current for k in ('date','hour','period')):
        h=current['hour'];period=current['period']
        if period not in ('am','pm','24h'):raise ValueError('오전·오후 확인')
        if period=='am':h%=12
        elif period=='pm':h=h%12+12
        request['departure']=f"{current['date']}T{h:02d}:{current.get('minute',0):02d}"
    questions=[('destination','집을 포함한 도착 위치를 지도에서 선택해 주세요.'),
               ('origin','출발 위치를 지도에서 선택해 주세요.')]
    for field,message in questions:
        if field not in request:return {'kind':'clarification','missing':[field],'message':message,'state':current,'stored':False}
    if 'departure' not in request:
        if 'date' not in current:field,message='date','출발 날짜를 YYYY-MM-DD로 알려 주세요.'
        elif 'hour' not in current:field,message='hour','몇 시에 출발하나요? 오전·오후도 알려 주세요.'
        else:field,message='period','오전인가요, 오후인가요?'
        return {'kind':'clarification','missing':[field],'message':message,'state':current,'stored':False}
    check_schema('route_request',request)
    return {'kind':'route_ready','request':request,'state':current,'stored':False,
            'message':'확인된 날짜·시각과 위치로 요청을 준비했습니다. 실제 경로 계산 완료는 아닙니다.'}
