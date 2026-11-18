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
