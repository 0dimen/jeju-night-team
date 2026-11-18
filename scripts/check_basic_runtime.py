"""키·모델·네트워크 없이 기본 시연을 점검한다. 실제 자료·센터 합격 판정과 별도다."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import socket
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def check():
    # 존재하는 키도 쓰지 않고, 연결 시도를 차단한다. 키 값과 사용자 자료는 출력하지 않는다.
    for key in ('GEMINI_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY'):
        os.environ.pop(key,None)
    attempts=[]
    original=socket.socket.connect
    def denied(*args,**kwargs):
        attempts.append('blocked')
        raise RuntimeError('기본 실행 점검 중 네트워크 연결 금지')
    socket.socket.connect=denied
    checks={}
    try:
        from agent.file_lock import process_lock
        with process_lock('jeju-night-runtime-check.lock'):
            checks['platform_file_lock']=True
        from agent.orchestrator import NightAgent
        agent=NightAgent()
        request=json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text(encoding='utf-8'))
        route=agent.route(request)
        checks['synthetic_route']=bool(route)
        emergency=agent.run('누가 따라와요')
        checks['emergency']=emergency.get('kind')=='emergency' and '112' in emergency.get('message','')
        report=agent.run('가로등 고장 제보',{'lat':33.5,'lng':126.5})
        checks['report_pending']='UNDER_REVIEW' in json.dumps(report)
        from fastapi.testclient import TestClient
        from agent.api import app
        with TestClient(app) as client:
            health=client.get('/health')
            checks['api_health']=health.status_code==200 and health.json().get('synthetic') is True
            response=client.post('/agent/chat',json={'text':'누가 따라와요'})
            checks['api_emergency']=response.status_code==200 and response.json().get('kind')=='emergency'
        checks['no_network_attempts']=not attempts
    finally:
        socket.socket.connect=original
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'platform':platform.system(),
            'python':platform.python_version(),'dependencies':{p:version(p) for p in ('fastapi','httpx','jsonschema','PyYAML')},
            'checks':checks,'passed':all(checks.values()),
            'scope':'가상 자료 기본 실행. 실제 길·자료 사용 승인·관리자 권한·센터 전체 동작은 확인하지 않음'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='점검 결과 JSON 저장 경로(선택)')
    args=parser.parse_args()
    try:result=check()
    except Exception as error:
        # 예외 메시지에 키나 사용자 경로가 섞일 수 있어 유형만 공개한다.
        result={'passed':False,'error_type':type(error).__name__,
                'help':'requirements-base.txt 설치와 Python 실행 환경을 확인하세요.'}
    text=json.dumps(result,ensure_ascii=False,indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
    raise SystemExit(0 if result['passed'] else 1)
