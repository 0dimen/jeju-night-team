"""제공 시안의 화면 구성·단계·뒤로가기·긴급 가시성을 로컬 실제 계산으로 검사."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect


def run():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not any(x in k for x in ('KEY','TOKEN','SECRET'))}
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','agent.api:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    shots=Path('/tmp/jeju-lab-shots');shots.mkdir(exist_ok=True)
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
                else:external.append('external');route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/lab')
            assert page.locator('.feature-grid button').count()==5
            page.screenshot(path=str(shots/'reference-home.png'))
            page.click('.search')
            assert page.locator('#live-origin-query').is_visible()
            assert not page.locator('#facility-button').is_visible() and not page.locator('#compare-button').is_visible()
            assert page.locator('#screen-title').inner_text()=='이동 조건 입력'
            page.screenshot(path=str(shots/'reference-route-input.png'))
            page.locator('#research-tools > summary').click();page.select_option('#facility-preference','cctv');page.click('#facility-button')
            page.wait_for_selector('#facility-result .route-choice')
            assert page.locator('#facility-result .route-choice').count()==2
            assert page.locator('#screen-title').inner_text()=='경로 비교'
            page.screenshot(path=str(shots/'reference-route-comparison.png'))
            page.locator('#facility-result').get_by_role('button',name='선택한 경로의 비교 근거 보기').click()
            assert page.locator('#facility-result .route-detail .metric').count()==4
            assert page.locator('#screen-title').inner_text()=='경로 상세'
            page.screenshot(path=str(shots/'reference-route-detail.png'))
            page.locator('#facility-result').get_by_role('button',name='이 경로 선택하기').click()
            assert page.locator('#screen-title').inner_text()=='선택한 이동 경로'
            page.screenshot(path=str(shots/'reference-route-selected.png'))
            page.click('#screen-back');assert page.locator('#screen-title').inner_text()=='경로 상세'
            page.click('#screen-back');assert page.locator('#screen-title').inner_text()=='경로 비교'
            page.click('#screen-back');assert page.locator('#screen-title').inner_text()=='이동 조건 입력'
            page.fill('#research-chat-input','누가 계속 따라와요');page.click('#research-chat-send')
            expect(page.locator('#research-chat-result .error')).to_contain_text('112')
            assert page.locator('#research-tools').get_attribute('open') is not None
            for width in (320,390,430,1024):
                page.set_viewport_size({'width':width,'height':844})
                for screen in ('home','route','report','data','my'):
                    page.click(f'nav [data-screen={screen}]');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,screen)
            page.set_viewport_size({'width':390,'height':844});page.click('nav [data-screen=report]')
            page.fill('#report-text','탑동광장 입구 쪽 가로등이 꺼져 있었어요.')
            assert page.locator('#screen-title').inner_text()=='상세 설명 작성'
            page.screenshot(path=str(shots/'reference-report.png'))
            assert not errors and not external
            browser.close()
        result={'home_three_plus_two':True,'live_search_primary':True,'examples_collapsed':True,'comparison_detail_selection':True,'back_navigation_by_stage':True,'emergency_visible_after_clear':True,'report_focus_step':True,'widths':[320,390,430,1024],'screens':5,'external_requests':0,'javascript_errors':0,'screenshots':6,'scope':'실제 공개 OSM 도로망·시설 계산. TMAP·VWorld 외부 호출 없이 화면과 구조 검증.'}
        Path('/tmp/jeju-design-reference-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill()
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
