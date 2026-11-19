"""공개 구간 전용 대화. 임의 주소를 공개 끝점으로 대체하지 않는다."""
import re
from agent.conversation import page_turn
from agent.intent import parse, outside_service_action, out_of_scope_action
from agent.report import emergency_check
from agent.data.research_router import get_router

PAIRS={'yeondong':('삼무공원','누웨마루'), 'seogwipo':('중앙로','올레시장')}
SCOPE='연동 공개 구간 또는 서귀포 공개 구간 중 골라 주세요. 집·임의 주소·반대 방향은 이 공개 구간 대화에서 지원하지 않습니다.'


def research_turn(text,state=None):
    # 긴급·자료·제보는 위치와 시간 질문보다 먼저 기존 규칙으로 처리한다.
    if emergency_check(text) or outside_service_action(text) or out_of_scope_action(text) or text.strip() in ('취소','초기화','대화 초기화') or parse(text)['kind'] in ('data_question','report'):
        result=page_turn(text,{})
        if result['kind']=='delegate':
            from agent.api import agent
            result={**agent.run(text),'state':{}}
        return result
    if not isinstance(state,(dict,type(None))):raise ValueError('상태 확인')
    state=state or {};region=state.get('region')
    route_provider=state.get('route_provider','osm')
    if route_provider not in ('osm','tmap'):route_provider='osm'
    if '티맵' in text or 'tmap' in text.lower():route_provider='tmap'
    elif '공개 도로망' in text or 'osm' in text.lower():route_provider='osm'
    explicit=None
    for key,(start,end) in PAIRS.items():
        if (start in text and end in text and text.index(start)<text.index(end)) or ('공개 구간' in text and ('연동' if key=='yeondong' else '서귀포') in text):explicit=key
    # 이전 지역이 있더라도 새 주소나 역방향 요청을 무시하지 않는다.
    followup=bool(re.fullmatch(r'[\d\sT:.,\-년월일시오전후분반새벽아침낮저녁밤출발할게요에은는으로위주가로등조명빠른최단길선호함께그리고둘다변경해줘CCTVcctvTMAPtmap티맵공개도로망osm]+',text.strip()))
    if re.search(r'집|대학교|초등학교|공항|시청',text):explicit=None;region=None
    if explicit:region=explicit
    elif region not in PAIRS or not followup:
        return {'kind':'clarification','missing':['supported_region'],'message':SCOPE,'state':{},'stored':False}
    previous={} if explicit and explicit!=state.get('region') else state.get('page',{})
    # 클라이언트가 보낸 개인 위치·완성된 출발값을 신뢰하지 않는다.
    previous={k:v for k,v in previous.items() if k in ('date','hour','minute','period')} if isinstance(previous,dict) else {}
    preference=state.get('preference','both')
    if preference not in ('fastest','cctv','light','both'):preference='both'
    cctv='cctv' in text.lower();light=any(x in text for x in ('가로등','조명'))
    if cctv or light:preference='both' if cctv and light else 'cctv' if cctv else 'light'
    if '함께' in text or '둘 다' in text:preference='both'
    if '빠른' in text or '최단' in text:preference='fastest'
    router=get_router(region)
    start,end=PAIRS[region]
    request={'origin':{'name':start,'lng':router.start[0],'lat':router.start[1]},'destination':{'name':end,'lng':router.goal[0],'lat':router.goal[1]},'preferences':['none']}
    previous.update(request=request,awaiting_route=True)
    # 장소 해석은 이 모듈에서 검증된 공개 구간만 사용한다.
    temporal=re.sub(r'삼무공원|누웨마루|중앙로|올레시장|티맵|TMAP|tmap|공개 도로망|OSM|osm','',text)
    result=page_turn(temporal,previous)
    public_state={'region':region,'preference':preference,'route_provider':route_provider,'page':{k:v for k,v in result.get('state',{}).items() if k in ('date','hour','minute','period')}}
    if result['kind']!='route_ready':return {**result,'state':public_state}
    if route_provider=='tmap':
        from agent.data.tmap_routes import compare
        calculated=compare(router,preference)
    else:calculated=router.route(preference)
    return {**calculated,'state':public_state,'stored':False,'departure':result['request']['departure'],
            'message':'확인한 날짜·시각으로 공개 구간 후보를 계산했습니다.',
            'time_effect':'날짜·시각은 확인했지만 현재 시설 위치 계산에는 시간별 밝기·통행 상태가 반영되지 않습니다.'}
