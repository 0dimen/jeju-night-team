"""서비스 화면(/app)만 검사: 확인용 도구 분리, 준비 중 메뉴, 장소 검색 제보, 긴급 안내, 화면 폭, 확인 화면(/lab) 분리."""
import os,json,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect


def run():
    keys=[os.environ.get(k) for k in ('VWORLD_API_KEY','TMAP_APP_KEY')]
    if not all(keys):raise RuntimeError('두 지도 키가 필요합니다. 값은 출력하지 않습니다.')
    shots=Path('docs/screenshots');shots.mkdir(exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not any(s in k for s in ('KEY','TOKEN','SECRET')) or k in ('VWORLD_API_KEY','TMAP_APP_KEY')}
    env['JEJU_OPEN_DATA_DIR']='/tmp/jeju-raw-data-not-present'
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                with urlopen(base+'/health',timeout=.2):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('서버 시작 실패')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context(viewport={'width':390,'height':844});external=[];leaks=[];errors=[]
            def guard(route):
                req=route.request
                if any(key in req.url or key in str(req.headers) for key in keys):leaks.append('key')
                if '?' in req.url and req.url.startswith(base+'/'):leaks.append('query_in_url')
                if req.url.startswith(base+'/') or req.url.startswith('blob:'):route.continue_()
                else:external.append('external');route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/app');page.wait_for_selector('.feature-grid')
            # 확인용 도구는 서비스 화면에 없다
            for selector in ('#research-tools','#synthetic-tools','#facility-form','#research-chat-form','#route-form','#chat-form','.connection-panel'):
                assert page.locator(selector).count()==0,selector
            assert '합성' not in page.content() and '연구용' not in page.content()
            assert page.locator('.feature-grid button').count()==5
            page.screenshot(path=str(shots/'service-home.png'))
            # 준비 중 메뉴
            for soon,title in (('population','유동인구 분석'),('issues','시설 이슈')):
                page.click(f'.feature-grid [data-soon={soon}]')
                expect(page.locator('#soon-title')).to_have_text(title);expect(page.locator('#screen-title')).to_have_text(title)
                page.click('#screen-back')
            page.click('.feature-grid [data-soon=population]');page.screenshot(path=str(shots/'service-soon.png'));page.click('#screen-back')
            # 경로 입력 화면
            page.click('nav [data-screen=route]');expect(page.locator('#route-input')).to_be_visible()
            page.screenshot(path=str(shots/'service-route-input.png'))
            # 제보: 위치 없이 확인하면 막힘
            page.click('nav [data-screen=report]')
            page.fill('#report-text','가로등이 꺼져 있었어요');page.click('#report-preview-button')
            expect(page.locator('#report-result .error')).to_contain_text('문제 위치')
            # 장소 검색으로 위치 선택
            page.fill('#report-place-query','탑동광장');page.click('#report-place-search')
            page.wait_for_selector('#report-place-candidates button',timeout=30000);page.locator('#report-place-candidates button').first.click()
            expect(page.locator('#report-place-selected')).to_contain_text('선택:')
            page.select_option('#report-facility','streetlight');page.select_option('#report-problem','not_working')
            page.fill('#report-text','편의점 옆 가로등이 꺼져 있었어요. 010-1234-5678로 연락 주세요');page.click('#report-preview-button')
            expect(page.locator('#report-confirm')).to_be_visible(timeout=20000)
            page.screenshot(path=str(shots/'service-report.png'),full_page=True)
            page.check('#report-consent');page.click('#report-submit')
            expect(page.locator('#receipt')).to_contain_text('제보가 접수됐어요',timeout=20000)
            expect(page.locator('#receipt')).to_contain_text('검토 대기')
            expect(page.locator('nav [data-screen=my]')).to_have_attribute('aria-current','page')
            page.screenshot(path=str(shots/'service-my.png'))
            # 긴급 표현은 112 안내를 먼저
            page.click('nav [data-screen=report]')
            page.fill('#report-place-query','탑동광장');page.click('#report-place-search')
            page.wait_for_selector('#report-place-candidates button',timeout=30000);page.locator('#report-place-candidates button').first.click()
            page.fill('#report-text','누가 계속 따라와요');page.click('#report-preview-button')
            expect(page.locator('#report-result')).to_contain_text('112',timeout=20000)
            assert page.locator('#report-confirm').is_hidden()
            # GPS: 거부 → 안내, 제주 밖 → 안내, 제주 안 → 선택 후 접수
            page.click('nav [data-screen=report]');page.click('#report-gps')
            expect(page.locator('#report-place-candidates .error')).to_contain_text('권한',timeout=20000)
            context.grant_permissions(['geolocation'],origin=base)
            context.set_geolocation({'latitude':37.5665,'longitude':126.978,'accuracy':20})
            page.click('#report-gps');expect(page.locator('#report-place-candidates .error')).to_contain_text('제주 밖',timeout=20000)
            context.set_geolocation({'latitude':33.517,'longitude':126.525,'accuracy':25})
            page.click('#report-gps');expect(page.locator('#report-place-selected')).to_contain_text('현재 위치 · 정확도 약 25m',timeout=20000)
            page.select_option('#report-facility','streetlight');page.select_option('#report-problem','not_working')
            page.fill('#report-text','골목 입구 가로등이 꺼져 있었어요');page.click('#report-preview-button')
            expect(page.locator('#report-confirm')).to_be_visible(timeout=20000)
            page.screenshot(path=str(shots/'service-report-gps.png'),full_page=True)
            page.check('#report-consent');page.click('#report-submit')
            expect(page.locator('#receipt')).to_contain_text('위치: 현재 위치',timeout=20000)
            context.clear_permissions()
            # 데이터 화면
            page.click('nav [data-screen=data]');page.click('#data-sources > summary')
            expect(page.locator('#data-sources')).to_contain_text('행정안전부');assert '합성' not in page.locator('#data').inner_text()
            for width in (320,390,430):
                page.set_viewport_size({'width':width,'height':844})
                for screen in ('home','route','report','data','my'):
                    page.click(f'nav [data-screen={screen}]');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,screen)
            # 새로고침하면 위치 입력이 지워진다
            page.set_viewport_size({'width':390,'height':844});page.reload();page.click('nav [data-screen=report]')
            assert page.input_value('#report-place-query')==''
            assert not any(key in page.content() for key in keys)
            # 확인 화면은 /lab 에 따로 있다
            page.goto(base+'/lab');page.wait_for_selector('#research-tools',state='attached');assert page.locator('#synthetic-tools').count()==1
            assert not external and not leaks and not errors,(external,leaks,errors)
            browser.close()
        return {'lab_tools_removed_from_app':True,'soon_screens':2,'report_place_search':True,'report_submitted':True,'gps_denied_out_of_jeju_and_ok':True,'emergency_112_first':True,'data_sources':True,'widths':[320,390,430],'lab_separate':True,'external_browser_requests':0,'keys_in_browser':0,'javascript_errors':0,'screenshots':6}
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill()
if __name__=='__main__':
    result=run();Path('/tmp/jeju-service-browser.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
