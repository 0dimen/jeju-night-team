"""설치된 Chromium으로 로컬 합성 화면 검사. 추가 브라우저 다운로드 없음."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def run():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={key:value for key,value in os.environ.items() if key not in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY')}
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','agent.api:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urlopen(base+'/health',timeout=.2):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('로컬 서버 시작 실패')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context();external=[];errors=[]
            def guard(route):
                if route.request.url.startswith(base+'/'):route.continue_()
                else:external.append(route.request.url);route.abort()
            context.route('**/*',guard)
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'/demo');page.wait_for_selector('#conversation')
            page.click('#locations')
            def send(text):
                page.fill('#text',text)
                with page.expect_response(lambda response:response.url.endswith('/agent/conversation')) as pending:
                    page.click('button[type=submit]')
                payload=pending.value.json()
                page.wait_for_timeout(100)
                return payload
            assert send('안전한 길 알려줘')['missing']==['date']
            assert send('2026-11-19')['missing']==['hour']
            assert send('3시')['missing']==['period']
            assert send('오후')['kind']=='route'
            assert page.locator('#result tbody tr').count()==2
            assert '안전 확률' in page.locator('#result').inner_text()
            page.click('#reset');assert page.locator('#result tbody tr').count()==0
            assert send('집으로 가는 길 알려줘')['missing']==['destination']
            page.click('#locations');page.fill('#text','남으면 안 되는 임시 입력')
            page.goto(base+'/health');page.go_back();page.wait_for_selector('#conversation')
            assert page.input_value('#text')==''
            assert page.locator('#location-status').inner_text()=='선택한 위치 없음'
            assert send('집으로 가는 길 알려줘')['missing']==['destination']
            page.click('#locations');page.reload()
            assert send('집으로 가는 길 알려줘')['missing']==['destination']
            source=send('CCTV 정보는 어디서 가져왔어요?');assert source['kind']=='data_question'
            assert send('CCTV와 가로등이 모두 고장 났어요')['kind']=='report_preview'
            assert '저장·게시하지 않았습니다' in page.locator('#result').inner_text()
            assert send('항공권 예약해줘')['kind']=='unsupported'
            assert page.evaluate('localStorage.length + sessionStorage.length')==0
            assert not external and not errors
            browser.close()
            return {'browser':'system Chromium','checks':['대화 날짜·오전오후','합성 비교표','초기화','실제 뒤로가기','새로고침','출처','제보 미저장','예약 범위 안내','브라우저 저장소 없음'], 'external_requests':len(external),'page_errors':errors,'scope':'로컬 합성 화면 검사. 실제 지도·센터·현장 검사 아님'}
    finally:
        proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
