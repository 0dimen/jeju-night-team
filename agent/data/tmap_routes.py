"""공개 두 구간의 TMAP 보행 후보. 사용자 주소·키·응답 원문은 저장하지 않는다."""
import hashlib,json,logging,math,os,time
from datetime import datetime,timezone
from pathlib import Path
from threading import RLock
import httpx
from agent.data.facility_route import project
from agent.geometry import covered_length

URL='https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1'
OPTIONS={'10':'최단 옵션','4':'대로 우선 옵션','30':'계단 제외 옵션'}
_lock=RLock();_last_call=0.;_blocked_until=0.
class TmapUnavailable(Exception):pass

class RedactKey(logging.Filter):
    def filter(self,record):
        key=os.environ.get('TMAP_APP_KEY','')
        if key:record.msg=record.getMessage().replace(key,'[REDACTED]');record.args=()
        return True
for _logger in ('httpx','httpcore.http11','httpcore.http2','httpcore.connection','httpcore.proxy'):
    logging.getLogger(_logger).addFilter(RedactKey())


def normalized(data,router,option):
    if not isinstance(data,dict) or data.get('type')!='FeatureCollection':raise ValueError('보행 응답 형식 확인')
    features=data.get('features');coords=[];distance=duration=None
    if not isinstance(features,list) or not 1<=len(features)<=10000:raise ValueError('응답 선분 수 확인')
    for feature in features:
        if not isinstance(feature,dict):raise ValueError('경로 요소 형식 확인')
        props=feature.get('properties',{})
        if not isinstance(props,dict):raise ValueError('경로 속성 확인')
        if props.get('totalDistance') is not None:distance=props['totalDistance']
        if props.get('totalTime') is not None:duration=props['totalTime']
        geom=feature.get('geometry',{})
        if not isinstance(geom,dict):raise ValueError('경로 형상 형식 확인')
        if geom.get('type')!='LineString':continue
        line=geom.get('coordinates')
        if not isinstance(line,list) or len(line)<2:raise ValueError('선분 좌표 확인')
        for p in line:
            if not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or not(125<=p[0]<=128 and 32<=p[1]<=34):raise ValueError('제주 좌표 확인')
        if coords and coords[-1]!=line[0]:raise ValueError('끊어진 경로를 임의로 연결하지 않습니다.')
        coords.extend(line if not coords else line[1:])
        if len(coords)>10000:raise ValueError('경로 점 수 초과')
    if len(coords)<2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (distance,duration)):raise ValueError('제공 거리·시간·형상 확인')
    xy=[project(router.graph,p) for p in coords]
    length=sum(math.dist(a,b) for a,b in zip(xy,xy[1:]))
    if not length or abs(length-distance)>max(10,distance*.1):raise ValueError('제공 거리와 형상 길이 차이 확인 필요')
    gaps=[math.dist(xy[0],project(router.graph,router.start)),math.dist(xy[-1],project(router.graph,router.goal))]
    if max(gaps)>80:raise ValueError('요청 끝점과 제공 경로의 차이가 큽니다.')
    return {'coordinates':coords,'provider_distance_m':distance,'provider_duration_seconds':duration,'geometry_length_m':round(length,1),'endpoint_snap_m':[round(g,1) for g in gaps],'option':option}


def cache_path(router,option):
    key=os.environ.get('TMAP_APP_KEY','')
    digest=hashlib.sha256(json.dumps([router.start,router.goal,option,key]).encode()).hexdigest()
    return Path(os.environ.get('TMAP_PUBLIC_CACHE_DIR','/tmp/jeju-night-tmap-public-cache'))/(digest+'.json')


def fetch_route(router,option,allow_cache=True):
    global _last_call,_blocked_until
    if option not in OPTIONS:raise ValueError('보행 옵션 확인')
    key=os.environ.get('TMAP_APP_KEY','').strip()
    if not key:raise TmapUnavailable('보행 API 키 미설정')
    path=cache_path(router,option) if allow_cache else None
    with _lock:
        if path is not None and path.exists() and time.time()-path.stat().st_mtime<3600:
            # 캐시에는 공개 구간의 정규화한 숫자·좌표만 보관한다.
            try:
                saved=json.loads(path.read_text());result=normalized(saved['geojson'],router,option);result['cached']=True;result['fetched_at']=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat();return result
            except (ValueError,KeyError,TypeError):path.unlink(missing_ok=True)
        if time.monotonic()<_blocked_until:raise TmapUnavailable('API 한도·인증 확인 후 다시 요청')
        time.sleep(max(0,1-(time.monotonic()-_last_call)))
        body={'startX':router.start[0],'startY':router.start[1],'endX':router.goal[0],'endY':router.goal[1],
              'startName':'start','endName':'end','reqCoordType':'WGS84GEO','resCoordType':'WGS84GEO','searchOption':option}
        _last_call=time.monotonic()
        try:
            with httpx.Client(timeout=12,follow_redirects=False) as client:
                with client.stream('POST',URL,headers={'appKey':key},json=body) as response:
                    if response.status_code!=200:
                        if response.status_code in (401,403,429):_blocked_until=time.monotonic()+60
                        raise TmapUnavailable('보행 API 응답 확인 필요')
                    raw=bytearray()
                    for part in response.iter_bytes():
                        raw.extend(part)
                        if len(raw)>2_000_000:raise TmapUnavailable('보행 응답 크기 초과')
            result=normalized(json.loads(raw),router,option)
        except (httpx.HTTPError,ValueError,KeyError,TypeError):raise TmapUnavailable('보행 API 응답 형식·연결 확인 필요') from None
        geojson={'type':'FeatureCollection','features':[{'properties':{'totalDistance':result['provider_distance_m'],'totalTime':result['provider_duration_seconds']},'geometry':{'type':'LineString','coordinates':result['coordinates']}}]}
        if path is not None:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({'geojson':geojson},separators=(',',':')))
        result['cached']=False;result['fetched_at']=datetime.now(timezone.utc).isoformat();return result


def coverage(router,coords,radius,kind):
    xy=[project(router.graph,p) for p in coords]
    # 배포용 자료의 시설 생략 범위 밖에서는 0%라고 표시하지 않는다.
    bounds=[v['xy'] for v in router.graph.get('nodes',{}).values()]
    if getattr(router,'coverage_scope',None)=='jeju':
        x0,y0=project(router.graph,(125,32));x1,y1=project(router.graph,(128,34))
    else:
        x0=min(p[0] for p in bounds);x1=max(p[0] for p in bounds);y0=min(p[1] for p in bounds);y1=max(p[1] for p in bounds)
    if any(not(x0<=x<=x1 and y0<=y<=y1) for x,y in xy):
        raise ValueError('공개 연구 시설 자료의 보장 범위 밖 경로입니다.')
    minx=min(p[0] for p in xy)-radius;maxx=max(p[0] for p in xy)+radius
    miny=min(p[1] for p in xy)-radius;maxy=max(p[1] for p in xy)+radius
    facilities=[]
    for p in getattr(router,kind):
        x,y=project(router.graph,p)
        if minx<=x<=maxx and miny<=y<=maxy:facilities.append({'x':x,'y':y})
    from agent.geometry import indexed_covered_length
    covered,total=indexed_covered_length(xy,facilities,radius)
    return round(covered/total*100,2)


def compare(router,preference='both',light_radius=15,cctv_radius=50,weight=4,max_detour=1.5):
    # 기존 설정 범위 검사는 계산기와 동일하게 적용한다.
    if preference not in ('fastest','cctv','light','both') or not(0<light_radius<=80 and 0<cctv_radius<=200 and 0<=weight<=16 and 1<=max_detour<=2):raise ValueError('비교 설정 확인')
    candidates=[];failures=[]
    for option,label in OPTIONS.items():
        try:
            row=fetch_route(router,option,allow_cache=False) if getattr(router,'private_request',False) else fetch_route(router,option)
            row['cctv_percent']=coverage(router,row['coordinates'],cctv_radius,'cctv')
            row['light_percent']=coverage(router,row['coordinates'],light_radius,'lights')
        except (TmapUnavailable,ValueError):failures.append(option);continue
        existing=next((r for r in candidates if r['coordinates']==row['coordinates']),None)
        if existing:
            existing['options'].append(option)
            existing['option_summaries'].append({'option':option,'distance_m':row['provider_distance_m'],'duration_seconds':row['provider_duration_seconds']})
            continue
        segments=len(row['coordinates'])-1
        row.update(options=[option],option_summaries=[{'option':option,'distance_m':row['provider_distance_m'],'duration_seconds':row['provider_duration_seconds']}],label='TMAP '+label,distance_m=row['provider_distance_m'],duration_minutes=round(row['provider_duration_seconds']/60,2),
                   walk_review={'status':'unavailable','reviewed_segments':0,'total_segments':segments,'message':'보행자 API 경로이며 지도·현장 통행 확인은 별도입니다.'})
        candidates.append(row)
    if not candidates:raise TmapUnavailable('계산 가능한 보행 후보가 없습니다.')
    candidates.sort(key=lambda r:r['distance_m'])
    for i,row in enumerate(candidates):row['id']='SHORTEST' if i==0 else 'TMAP_'+row['options'][0]
    lw=weight if preference in ('light','both') else 0;cw=weight if preference in ('cctv','both') else 0
    eligible=[r for r in candidates if r['distance_m']<=candidates[0]['distance_m']*max_detour]
    for row in candidates:
        row['eligible_for_recommendation']=row['distance_m']<=candidates[0]['distance_m']*max_detour
        row['comparison_cost']=round(row['geometry_length_m']*(1+lw*(1-row['light_percent']/100)+cw*(1-row['cctv_percent']/100)),2)
    # 주어진 최대 세 후보 사이의 비교다. 시설 우회 경로를 제공사에 생성시킨 것은 아니다.
    best=min(eligible,key=lambda r:(r['duration_minutes'],r['distance_m'])) if preference=='fastest' else min(eligible,key=lambda r:(r['comparison_cost'],r['distance_m']))
    return {'kind':'facility_routes','provider':'tmap','synthetic':False,'research_only':True,'region':router.region,'label':router.label+' · TMAP 보행 후보',
        'routes':candidates,'recommended_route_id':best['id'],'same_route':len(candidates)==1,'preference':preference,
        'parameters':{'light_radius_m':light_radius,'cctv_radius_m':cctv_radius,'requested_weight':weight,'weights_used':{'light':lw,'cctv':cw},'max_detour':max_detour,'ranking_only':True},
        'sources':{**router.sources,'roads':{'name':'TMAP 보행자 경로안내','source_url':'https://tmap-skopenapi.readme.io/reference/보행자-경로안내'}},
        'endpoint_snap_m':candidates[0]['endpoint_snap_m'],'failed_options':failures,
        'reason':f"TMAP 최단·대로 우선·계단 제외 옵션에서 서로 다른 후보 {len(candidates)}개를 비교했습니다. 같은 형상은 합쳤습니다."+(' 일부 옵션은 응답·시설 범위 확인을 통과하지 못해 제외했습니다.' if failures else ''),
        'limitations':['제공사 보행 경로이며 현재 통행·현장 보도·폐쇄를 실측한 결과가 아닙니다.','거리·시간은 TMAP 제공 추정값이고 시설 인접 비율은 반환 형상에서 별도로 계산합니다.','시설 가중치는 받은 후보의 비교에만 사용합니다. 제공사 경로를 CCTV·조명 기준으로 새로 생성한 것은 아닙니다.','지도 API와 시설 자료는 최신성·촬영·밝기·작동·안전을 보장하지 않습니다.','인접 비율은 공개 목록 기준이며 0%여도 실제 시설이 없다는 뜻은 아닙니다.','공개 구간 두 곳만 지원하며 집·임의 주소를 제공사에 보내거나 저장하지 않습니다.','반경·가중치·우회 한도는 연구용 설정입니다. 빠른 길은 주어진 후보의 제공 예상 시간으로 비교합니다.']}
