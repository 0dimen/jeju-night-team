"""선택한 위치의 일회성 경로 계산. 위치·요청·경로를 서버 캐시에 넣지 않는다."""
import json,math,os,re
from pathlib import Path
from types import SimpleNamespace
from functools import lru_cache
from agent.data.research_router import ROOT,get_router
from agent.data.facility_route import project
from agent.data.tmap_routes import compare
from agent.maps.vworld import public_points


@lru_cache(maxsize=2)
def _compiled(path,mtime,size):
    if size>20_000_000:raise ValueError('제주 시설 자료 크기 제한')
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version')!=1:raise ValueError('제주 시설 자료 버전 확인')
    return data


def load_facilities(source):
    if source not in ('standard','datahub'):raise ValueError('시설 원본 확인')
    folder=os.environ.get('JEJU_COMPILED_DATA_DIR')
    if folder:
        path=Path(folder)/'jeju_facilities.json';stat=path.stat();d=_compiled(str(path),stat.st_mtime_ns,stat.st_size)
        return d['lights'],d['cctv'][source],d['light_sources'],d['cctv_sources'][source]
    city=get_router('yeondong',source);seogwipo=get_router('seogwipo',source)
    return city.lights+seogwipo.lights,city.cctv,{'yeondong':city.sources['light'],'seogwipo':seogwipo.sources['light']},city.sources['cctv']


def selected_context(origin,destination,source='standard'):
    for p in (origin,destination):
        if len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or not(125<=p[0]<=128 and 32<=p[1]<=34):raise ValueError('제주 위치 좌표 확인')
    graph={'center':tuple(origin),'scale':(math.cos(math.radians(origin[1]))*111320,110540)}
    distance=math.dist(project(graph,origin),project(graph,destination))
    if distance<5 or distance>20000:raise ValueError('현재 연구 기능은 직선거리 5m 이상 20km 이하만 지원합니다.')
    lights,cctv,light_sources,cctv_source=load_facilities(source)
    if not lights or not cctv:raise ValueError('시설 자료가 없습니다. 0으로 대신하지 않습니다.')
    return SimpleNamespace(start=tuple(origin),goal=tuple(destination),graph=graph,lights=lights,cctv=cctv,source=source,region='custom',
        label='선택한 출발지~도착지',coverage_scope='jeju',private_request=True,
        sources={'cctv':cctv_source,'light':{'basis_date':' / '.join(s['basis_date'] for s in light_sources.values()),'selected_rows':len(lights),'source_rows':sum(s['source_rows'] for s in light_sources.values()),'sources':light_sources}})


def selected_compare(origin,destination,departure,source='standard',preference='both',light_radius=15,cctv_radius=50,weight=4,max_detour=1.5,*,criteria=None):
    from datetime import datetime
    if not isinstance(departure,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',departure):raise ValueError('날짜와 24시간 시각 확인')
    parsed=datetime.fromisoformat(departure)
    if parsed.tzinfo is not None:raise ValueError('한국 시간 기준의 날짜·24시간 시각을 입력해 주세요.')
    if criteria is not None:
        from agent.data.route_criteria import normalize_criteria
        criteria=normalize_criteria(criteria)
    context=selected_context(origin,destination,source)
    result=compare(context,preference,light_radius,cctv_radius,weight,max_detour)
    result.update(private_request=True,page_location_stored=False,stored=False,departure=parsed.isoformat(timespec='minutes'),
        time_effect='입력 시각은 한국 시간으로 확인했습니다. 보행 API의 실시간 밝기·통행·시각별 혼잡을 반영한 계산은 아닙니다.',
        map_points=public_points(context,result['routes']))
    result['limitations']=[s for s in result['limitations'] if '공개 구간 두 곳만' not in s]
    result['limitations'].extend(['선택 좌표는 TMAP으로 전달합니다. 앱 서버는 이 요청·경로를 파일·DB·캐시에 저장하지 않습니다.','시설 목록은 제주 두 시의 공개 좌표입니다. 누락·기준일 차이 때문에 실제 시설 존재·밝기를 모두 설명하지 못합니다.'])
    if criteria is not None:
        from agent.data.route_criteria import rank_selected_criteria
        result=rank_selected_criteria(result,criteria)
    return result
