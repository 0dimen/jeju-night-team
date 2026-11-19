"""설치 Chromium으로 웹앱과 실제 로컬 API 연결 검사. 외부 요청 차단."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def run():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY')}
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','agent.api:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urlopen(base+'/health',timeout=.2):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('서버 시작 실패')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context(viewport={'width':390,'height':844});external=[];errors=[]
            def guard(route):
                if route.request.url.startswith(base+'/'):route.continue_()
                else:external.append(route.request.url);route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'/app');page.wait_for_selector('.feature-grid')
            for width in (320,390,430):
                page.set_viewport_size({'width':width,'height':844})
                for screen in ('home','route','report','data','my'):
                    page.click(f'nav [data-screen={screen}]')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,screen)
            page.set_viewport_size({'width':390,'height':844});page.click('nav [data-screen=home]');page.screenshot(path='/tmp/jeju-nightway-home.png',full_page=True)
            page.click('.feature-grid [data-screen=route]');page.select_option('#origin','제주시청');page.select_option('#destination','탑동광장');page.fill('#departure-date','2026-11-20');page.fill('#departure-time','23:00')
            page.click('#compare-button');page.wait_for_selector('#route-result .route-card')
            assert page.locator('#route-result .route-card').count()==2
            assert page.locator('#route-result .route-card[aria-pressed=true]').get_attribute('data-route')=='B'
            page.click('#route-result .route-card[data-route=A]');assert page.locator('#route-result .route-card[aria-pressed=true]').get_attribute('data-route')=='A'
            assert '경로 A' in page.locator('#route-result .route-map').get_attribute('aria-label')
            page.screenshot(path='/tmp/jeju-nightway-route.png',full_page=True)
            page.check('[name=preference][value=none]');page.click('#compare-button');page.wait_for_timeout(300)
            assert page.locator('#route-result .route-card').first.get_attribute('data-route')=='A'
            page.route('**/agent/conversation',lambda route:route.fulfill(status=503,body='unavailable'))
            page.click('#compare-button');page.wait_for_selector('#route-result .error');assert page.input_value('#origin')=='제주시청'
            page.unroute('**/agent/conversation')
            page.fill('#chat-input','누가 계속 따라와요');page.click('#chat-send');page.wait_for_selector('#chat-result .error');assert '112' in page.locator('#chat-result').inner_text()
            assert page.input_value('#origin')==''
            page.fill('#chat-input','CCTV 자료 출처가 뭐야?');page.click('#chat-send');page.wait_for_selector('#chat-result h2')
            assert '자료 설명' in page.locator('#chat-result').inner_text()
            page.click('nav [data-screen=report]');page.select_option('#report-location','탑동광장');page.fill('#report-text','가로등이 꺼져 있어요.');page.click('#report-preview-button');page.wait_for_selector('#report-confirm:not([hidden])')
            page.check('#report-consent');page.click('#report-submit');page.wait_for_selector('#my:not([hidden])');assert 'SYNTHETIC-RPT-' in page.locator('#receipt').inner_text() and '검토 대기' in page.locator('#receipt').inner_text()
            page.click('nav [data-screen=report]');page.select_option('#report-location','동문시장');page.fill('#report-text','CCTV와 가로등이 모두 고장 났어요');page.click('#report-preview-button');page.wait_for_timeout(300);assert page.locator('#report-confirm').is_hidden()
            page.click('nav [data-screen=route]');page.select_option('#origin','동문시장');page.goto(base+'/health');page.go_back();page.wait_for_selector('#origin',state='attached');assert page.input_value('#origin')=='' and 'SYNTHETIC-RPT-' not in page.locator('#receipt').inner_text()
            page.reload();assert page.input_value('#origin')==''
            assert page.evaluate('localStorage.length+sessionStorage.length')==0
            assert not external and not errors
            browser.close()
        return {'widths':[320,390,430],'screens':5,'route_and_card_selection':True,'preference_changes_order':True,'failure_preserves_input':True,'emergency_clears_location':True,'preview_and_synthetic_submission':True,'ambiguous_report_not_submitted':True,'real_back_and_reload_clear':True,'external_requests':len(external),'javascript_errors':errors,'scope':'로컬 합성 웹앱·API. 실제 지도·GPS·센터·행정기관 아님'}
    finally:proc.terminate();proc.wait(timeout=10)

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
