"""저장한 키의 실제 타일→브라우저 지도 연결. 키 값·요청 URL은 출력하지 않는다."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect


def reveal(page,panel):
    if page.locator('#'+panel).get_attribute('open') is None:page.locator('#'+panel+' > summary').click()


def run(tmap=False):
    key=os.environ.get('VWORLD_API_KEY')
    if not key:raise RuntimeError('VWORLD_API_KEY 필요; 값은 출력하지 않습니다.')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not any(s in k for s in ('KEY','TOKEN','SECRET')) or k in ('VWORLD_API_KEY','TMAP_APP_KEY')}
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','agent.api:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urlopen(base+'/health',timeout=.2):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('로컬 서버 시작 실패')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context(viewport={'width':390,'height':844});external=[];leaks=[];tile_status=[];errors=[]
            def guard(route):
                if any(value and (value in route.request.url or value in str(route.request.headers)) for value in (key,os.environ.get('TMAP_APP_KEY'))):leaks.append('key_in_browser_request')
                if route.request.url.startswith(base+'/'):route.continue_()
                else:external.append('external_request');route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('response',lambda r:tile_status.append(r.status) if '/maps/vworld/tiles/' in r.url else None)
            page.goto(base+'/lab');page.click('nav [data-screen=route]');reveal(page,'research-tools');page.click('#tmap-button' if tmap else '#facility-button');page.wait_for_selector('#facility-result .route-card')
            page.get_by_role('button',name='VWorld 배경지도·시설 위치 불러오기').click()
            expect(page.locator('#facility-result')).to_contain_text('VWorld 배경지도 연결 완료',timeout=45000)
            page.wait_for_selector('.vworld-map circle title',state='attached')
            assert len(tile_status)>0 and all(code==200 for code in tile_status)
            assert page.locator('.vworld-map polyline').count()==(1 if tmap else 2)
            assert page.locator('.vworld-map circle title').count()>0
            page.locator('#facility-result .route-card[data-route=SHORTEST]').click()
            assert page.locator('.vworld-map polyline[data-route=SHORTEST]').get_attribute('opacity')=='1'
            for width in (320,390,430):
                page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width':390,'height':844});page.locator('.vworld-map').screenshot(path='/tmp/jeju-vworld-map.png')
            assert key not in page.content()
            assert not os.environ.get('TMAP_APP_KEY') or os.environ['TMAP_APP_KEY'] not in page.content()
            count=page.locator('.vworld-map circle title').count()
            page.click('nav [data-screen=home]');page.click('nav [data-screen=route]');assert page.locator('.vworld-map').count()==0
            assert not leaks and not external and not errors
            browser.close()
        return {'tmap_actual_routes':tmap,'actual_tile_requests':len(tile_status),'all_tiles_200':True,'facility_markers':count,'route_card_map_synced':True,'widths':[320,390,430],'navigation_cleared':True,'browser_key_exposures':0,'external_browser_requests':0,'javascript_errors':0}
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill()
if __name__=='__main__':
    result=run(tmap='--tmap' in sys.argv);Path('/tmp/jeju-tmap-browser.json' if '--tmap' in sys.argv else '/tmp/jeju-vworld-browser.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
