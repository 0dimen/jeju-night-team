from copy import deepcopy
from stubs.engine import analyze


def explanation_input(case,request):
    result=analyze(request,radius=80 if case['variant']=='large_radius' else 50)
    variant=case['variant']
    if variant in ('single','reanalysis_single'):
        result['routes']=result['routes'][:1]
        result['comparison']={'detour':'대안 경로 없음','rank_reason':'대안 경로 없음'}
    if variant=='empty_routes':
        result['routes']=[]
        result['comparison']={'detour':'비교할 경로 없음','rank_reason':'분석 가능한 경로 없음'}
    if variant in ('missing_all','cctv_missing','preference_unavailable'):
        keys=['cctv','streetlight','activity'] if variant=='missing_all' else ['cctv']
        for route in result['routes']:
            for key in keys: route['indicators'][key]={'status':'unavailable'}
        result['unavailable_preferences']=keys
    if variant=='tie':
        result['routes'][1]['indicators']=deepcopy(result['routes'][0]['indicators'])
        result['comparison']['rank_reason']='지표 동일; 이동 시간 비교'
    if variant=='pending':
        for route in result['routes']:
            route['indicators']['streetlight']={'status':'pending','display':'미검증 제보'}
    if variant=='all_historical':
        for route in result['routes']:
            for key in route['indicators']:
                route['indicators'][key]={'status':'historical','display':'SYNTHETIC 과거 월별 지역 집계; 현재 상태 아님'}
    if variant=='zero_verified':
        for route in result['routes']:
            route['indicators']['cctv']={'status':'verified','value':0.,'display':'확인한 합성 시설 인접 구간 0.0%'}
    if variant=='long_limitations':
        result['limitations']+=['SYNTHETIC 서로 다른 자료 기준일을 직접 합치지 않았습니다.']*5
    if variant=='no_sources':
        result['sources']=[]
        result['limitations'].append('출처 메타데이터를 확인하지 못했습니다.')
    return result
