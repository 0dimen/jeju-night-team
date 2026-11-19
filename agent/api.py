"""시연용 POST API. 실제 관리자 인증과 실제 엔진 연결은 서비스 담당 범위다."""
from fastapi import FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from jsonschema.exceptions import ValidationError
from agent.orchestrator import NightAgent

app = FastAPI(title='제주밤길 SYNTHETIC Agent', version='0.1.0')
agent = NightAgent()


@app.exception_handler(RequestValidationError)
async def invalid_input(request,exc):
    from agent.report import emergency_check
    from agent.common import load_yaml
    text=exc.body.get('text') if isinstance(exc.body,dict) else None
    if isinstance(text,str) and emergency_check(text):
        return JSONResponse(status_code=200,content={'kind':'emergency','stored':False,
            'message':load_yaml('registry/emergency_phrases.yaml')['message']})
    # 기본 오류 응답의 input 칸에 원문·개인정보·단정 문구를 되돌려 주지 않는다.
    return JSONResponse(status_code=422,content={'detail':'입력 형식과 길이를 확인해 주세요.'})


class ChatBody(BaseModel):
    text: str = Field(max_length=5000)
    context: dict = Field(default_factory=dict)


class RouteBody(BaseModel):
    request: dict
    radius: float = Field(default=50, gt=0, le=200)


@app.post('/agent/chat')
def chat(body: ChatBody):
    try:
        return agent.run(body.text,body.context)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, '입력 형식과 위치를 확인해 주세요.') from exc


@app.post('/routes/compare')
def routes(body: RouteBody):
    try:
        return agent.route(body.request,radius=body.radius)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, '입력 형식을 확인해 주세요.') from exc


@app.get('/health')
def health():
    return {'status':'ok','synthetic':getattr(agent.engine,'synthetic',True) is not False,'level':'L0','review_api':'제공 안 함; 시연용 SQLite 대역에서만 검증'}


class ReportPreviewBody(BaseModel):
    text: str = Field(max_length=5000)
    user_choice: dict = Field(default_factory=dict)


@app.post('/reports/preview')
def report_preview(body: ReportPreviewBody):
    from agent.report.preview import preview_report
    try:
        return preview_report(body.text,body.user_choice)
    except ValueError as exc:
        raise HTTPException(422,'허용된 시설·문제 항목을 확인해 주세요.') from exc


class ConversationBody(BaseModel):
    text: str = Field(max_length=5000)
    state: dict = Field(default_factory=dict)


@app.post('/agent/conversation')
def conversation(body: ConversationBody,response: Response):
    from agent.conversation import page_turn
    response.headers['Cache-Control']='no-store'
    response.headers['Pragma']='no-cache'
    try:
        result=page_turn(body.text,body.state)
        if result['kind']=='route_ready':
            from agent.comparison import comparison_table
            calculated=agent.route(result['request'])
            return {'kind':'route',**calculated,'comparison_table':comparison_table(calculated['analysis']),
                    'state':result['state'],'page_location_stored':False,
                    'message':('현재 결과는 합성 시설·경로 시연입니다. 입력한 실제 위치의 길찾기가 아닙니다.' if calculated['synthetic'] else '등록된 파일 경로를 계산했습니다. 현재 시설 상태를 보증하지 않습니다.')}
        if result['kind']=='delegate':
            # 시간과 무관한 요청은 기존 응답을 바로 돌려준다. 페이지 위치는 전달하지 않는다.
            return {**agent.run(body.text),'state':{},'page_location_stored':False}
        return result
    except (ValidationError,ValueError,TypeError,KeyError) as exc:
        raise HTTPException(422,'페이지 위치와 날짜·오전·오후 입력을 확인해 주세요.') from exc


@app.get('/demo', include_in_schema=False)
@app.get('/demo/{asset}', include_in_schema=False)
def demo_page(asset: str = 'demo.html'):
    from pathlib import Path
    from fastapi.responses import FileResponse
    if asset not in {'demo.html','demo.css','demo.mjs','page_conversation.mjs'}:
        raise HTTPException(404, '파일이 없습니다.')
    return FileResponse(Path(__file__).resolve().parents[1]/'client'/asset,headers={
        'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; connect-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


@app.get('/lab', include_in_schema=False)
@app.get('/lab/{asset}', include_in_schema=False)
def lab_page(asset: str = 'index.html'):
    """에이전트 확인용 화면. 서비스 화면(/app)과 분리한다."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    if asset not in {'index.html','app.mjs'}:
        raise HTTPException(404, '파일이 없습니다.')
    return FileResponse(Path(__file__).resolve().parents[1]/'client'/'lab'/asset, headers={
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; connect-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


@app.get('/app', include_in_schema=False)
@app.get('/app/{asset}', include_in_schema=False)
def nightway_app(asset: str = 'index.html'):
    from pathlib import Path
    from fastapi.responses import FileResponse
    if asset not in {'index.html','style.css','tokens.css','app.mjs','vworld.mjs','screens.mjs'}:
        raise HTTPException(404, '파일이 없습니다.')
    return FileResponse(Path(__file__).resolve().parents[1]/'client'/'nightway'/asset, headers={
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; connect-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


from typing import Literal


class FacilityRouteBody(BaseModel):
    region: Literal['yeondong','seogwipo']
    preference: Literal['fastest','cctv','light','both'] = 'both'
    cctv_source: Literal['standard','datahub'] = 'standard'
    light_radius: float = Field(default=15,gt=0,le=80)
    cctv_radius: float = Field(default=50,gt=0,le=200)
    weight: float = Field(default=4,ge=0,le=16)
    max_detour: float = Field(default=1.5,ge=1,le=2)


@app.post('/research/routes/facilities')
def facility_routes(body: FacilityRouteBody,response: Response):
    from agent.data.research_router import get_router
    response.headers['Cache-Control']='no-store'
    try:
        return get_router(body.region,body.cctv_source).route(body.preference,body.light_radius,body.cctv_radius,body.weight,body.max_detour)
    except FileNotFoundError as exc:
        raise HTTPException(503,'공개 연구 데이터가 없는 실행 환경입니다. 합성 결과로 대신하지 않습니다. 데이터 폴더를 별도 연결해 주세요.') from exc
    except (ValueError,KeyError,StopIteration) as exc:
        raise HTTPException(422,'연구 설정 또는 공개 데이터 형식을 확인해 주세요.') from exc


@app.post('/research/agent/conversation')
def research_conversation(body: ConversationBody,response: Response):
    from agent.research_conversation import research_turn
    from agent.data.tmap_routes import TmapUnavailable
    response.headers['Cache-Control']='no-store'
    response.headers['Pragma']='no-cache'
    try:
        return research_turn(body.text,body.state)
    except TmapUnavailable:
        raise HTTPException(503,'TMAP 보행 후보를 확인하지 못했습니다. 키·한도·시설 자료를 확인해 주세요. 합성 경로로 대신하지 않습니다.') from None
    except FileNotFoundError as exc:
        raise HTTPException(503,'공개 데이터가 없습니다. 합성 경로로 대신하지 않습니다.') from exc
    except (ValueError,TypeError,KeyError,ValidationError) as exc:
        raise HTTPException(422,'공개 구간과 날짜·오전·오후 입력을 확인해 주세요.') from exc


@app.get('/',include_in_schema=False)
def landing():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/app',status_code=307,headers={'Cache-Control':'no-store'})


@app.get('/data/population')
def population_stats():
    """제주데이터허브 748번에서 만든 읍면동·월별 거주·근무·방문인구 집계(scripts/build_population_stats.py)."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    path=Path(__file__).resolve().parents[1]/'data'/'population'/'jeju_emd_population_monthly.json'
    if not path.is_file():
        raise HTTPException(503,'유동인구 집계 자료가 없습니다. 지어낸 값으로 대신하지 않습니다.')
    return FileResponse(path,media_type='application/json',headers={'Cache-Control':'public, max-age=3600'})


@app.get('/runtime/status')
def runtime_status(response: Response):
    import json,os
    from pathlib import Path
    response.headers['Cache-Control']='no-store'
    compiled=os.environ.get('JEJU_COMPILED_DATA_DIR')
    if compiled:
        folder=Path(compiled)
        available=all((folder/f'{region}_{source}.json').is_file() for region in ('yeondong','seogwipo') for source in ('standard','datahub'))
        info=folder/'build_info.json'
        built_at=json.loads(info.read_text(encoding='utf-8')).get('built_at') if info.exists() else None
    else:
        folder=Path(os.environ.get('JEJU_OPEN_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data/open')))
        available=(folder/'foot_routes/collection_summary.json').is_file()
        built_at=None
    return {'facility_data_connected':available,'data_mode':'compiled' if compiled else 'source_files',
            'agent_mode':'rules_and_templates','external_llm_enabled':False,'built_at':built_at,
            'scope':'공개 구간 두 곳의 연구 시연. 집·임의 주소·실시간 통행 검증은 미지원.',
            'report_storage':'시연용 임시 메모리. 실제 민원 접수·영구 보관이 아닙니다.'}


@app.get('/maps/vworld/status')
def vworld_status(response: Response):
    import os
    response.headers['Cache-Control']='no-store'
    return {'configured':bool(os.environ.get('VWORLD_API_KEY','').strip()),'provider':'VWorld',
            'attribution':'공간정보 오픈플랫폼 VWorld · 국토교통부',
            'notice':'배경지도이며 보행 가능 여부·시설 작동·밝기의 확인 근거가 아닙니다.'}


@app.get('/maps/vworld/tiles/{z}/{x}/{y}.png')
def vworld_tile(z:int,x:int,y:int):
    from agent.maps.vworld import fetch_tile,MapUnavailable
    try:
        content=fetch_tile(z,x,y)
        return Response(content,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    except ValueError as exc:
        raise HTTPException(422,'지원하는 제주 지도 타일 범위가 아닙니다.') from None
    except MapUnavailable as exc:
        raise HTTPException(503,'배경지도를 불러오지 못했습니다. 키·도메인·제공사 연결을 확인해 주세요. 경로 수치는 유지됩니다.') from None


class FacilityMapBody(FacilityRouteBody):
    route_provider: Literal['osm','tmap']='osm'


@app.post('/research/maps/facilities')
def facility_map_points(body:FacilityMapBody,response:Response):
    from agent.maps.vworld import public_points
    from agent.data.research_router import get_router
    response.headers['Cache-Control']='no-store'
    try:
        router=get_router(body.region,body.cctv_source)
        if body.route_provider=='tmap':
            from agent.data.tmap_routes import compare,TmapUnavailable
            try:view=compare(router,body.preference,body.light_radius,body.cctv_radius,body.weight,body.max_detour)
            except TmapUnavailable:raise HTTPException(503,'보행 후보를 확인하지 못했습니다.') from None
        else:view=router.route(body.preference,body.light_radius,body.cctv_radius,body.weight,body.max_detour)
        return public_points(router,view['routes'])
    except FileNotFoundError:
        raise HTTPException(503,'공개 시설 자료가 없습니다.') from None
    except (ValueError,KeyError,StopIteration):
        raise HTTPException(422,'공개 지도 구간·연구 설정을 확인해 주세요.') from None


@app.post('/research/routes/tmap')
def tmap_routes(body:FacilityRouteBody,response:Response):
    from agent.data.research_router import get_router
    from agent.data.tmap_routes import compare,TmapUnavailable
    response.headers['Cache-Control']='no-store'
    try:
        return compare(get_router(body.region,body.cctv_source),body.preference,body.light_radius,body.cctv_radius,body.weight,body.max_detour)
    except (TmapUnavailable,FileNotFoundError):
        raise HTTPException(503,'TMAP 보행 후보를 불러오지 못했습니다. 키·이용 권한·한도·시설 자료 연결을 확인해 주세요. 합성 경로로 대신하지 않습니다.') from None
    except (ValueError,KeyError,TypeError):
        raise HTTPException(422,'공개 구간과 보행 비교 설정을 확인해 주세요.') from None


class PlaceSearchBody(BaseModel):
    query: str=Field(min_length=1,max_length=120)
    mode: Literal['place','road','parcel']='place'


@app.post('/maps/places/search')
def place_search(body:PlaceSearchBody,response:Response):
    from agent.maps.search import search_places,SearchUnavailable
    response.headers['Cache-Control']='no-store'
    try:
        candidates=search_places(body.query,body.mode)
        return {'kind':'place_candidates','candidates':candidates,'stored':False,
                'message':'주소와 위치를 확인하고 지점을 선택해 주세요.' if candidates else '제주 범위에서 검색 결과를 찾지 못했습니다. 더 구체적인 이름이나 도로명 주소를 입력해 주세요.'}
    except SearchUnavailable:
        raise HTTPException(503,'장소 검색을 처리하지 못했습니다. 키·연결·검색 방식을 확인해 주세요.') from None
    except ValueError:
        raise HTTPException(422,'제주 장소명이나 주소를 확인해 주세요.') from None


class SelectedPoint(BaseModel):
    lat: float=Field(ge=32,le=34)
    lng: float=Field(ge=125,le=128)


class SelectedRouteBody(BaseModel):
    origin: SelectedPoint
    destination: SelectedPoint
    departure: str=Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')
    preference: Literal['fastest','cctv','light','both']='both'
    cctv_source: Literal['standard','datahub']='standard'
    light_radius: float=Field(default=15,gt=0,le=80)
    cctv_radius: float=Field(default=50,gt=0,le=200)
    weight: float=Field(default=4,ge=0,le=16)
    max_detour: float=Field(default=1.5,ge=1,le=2)


@app.post('/research/routes/selected')
def selected_routes(body:SelectedRouteBody,response:Response):
    from agent.data.selected_routes import selected_compare
    from agent.data.tmap_routes import TmapUnavailable
    response.headers['Cache-Control']='no-store'
    response.headers['Pragma']='no-cache'
    try:
        return selected_compare([body.origin.lng,body.origin.lat],[body.destination.lng,body.destination.lat],body.departure,body.cctv_source,body.preference,body.light_radius,body.cctv_radius,body.weight,body.max_detour)
    except (TmapUnavailable,FileNotFoundError):
        raise HTTPException(503,'선택한 위치의 경로·시설 자료를 확인하지 못했습니다. 키·한도·자료 연결을 확인해 주세요. 합성 경로로 대신하지 않습니다.') from None
    except (ValueError,KeyError,TypeError):
        raise HTTPException(422,'제주 위치·날짜·24시간 시각과 지원 거리(직선 5m~20km)를 확인해 주세요.') from None


class MapTileBody(BaseModel):
    z:int=Field(ge=10,le=19)
    x:int=Field(ge=0)
    y:int=Field(ge=0)


@app.post('/maps/vworld/tile')
def private_map_tile(body:MapTileBody):
    # 페이지 한정 위치의 타일 번호도 브라우저 요청 URL에 남기지 않는다.
    return vworld_tile(body.z,body.x,body.y)
