"""공개 장소로 검색→선택→비저장 경로→POST 지도→페이지 초기화를 실제 검사."""
import os,json,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright,expect


def reveal(page,field):
    """출발지·목적지·시각 행은 눌러야 입력칸이 열린다. 결과 단계에서는 뒤로 가기로 입력 단계에 돌아간다."""
    for _ in range(3):
        if page.locator(f'#live-{field}-toggle').is_visible() or not page.locator('#screen-back').is_visible():break
        page.click('#screen-back')
    if page.locator(f'#live-{field}-panel').is_hidden():page.click(f'#live-{field}-toggle')


def run():
    keys=[os.environ.get(k) for k in ('VWORLD_API_KEY','TMAP_APP_KEY')]
    if not all(keys):raise RuntimeError('두 지도 키가 필요합니다. 값은 출력하지 않습니다.')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    remote=os.environ.get('JEJU_TEST_BASE_URL','').rstrip('/')  # 배포 주소를 직접 시험할 때
    if remote:base=remote
    env={k:v for k,v in os.environ.items() if not any(s in k for s in ('KEY','TOKEN','SECRET')) or k in ('VWORLD_API_KEY','TMAP_APP_KEY')}
    env['JEJU_OPEN_DATA_DIR']='/tmp/jeju-raw-data-not-present'
    cache=Path(os.environ.get('TMAP_PUBLIC_CACHE_DIR','/tmp/jeju-night-tmap-public-cache'));before=set(cache.glob('*.json'))
    proc=None if remote else subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                with urlopen(base+'/health',timeout=10 if remote else .2):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('서버 시작 실패')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context(viewport={'width':390,'height':844});external=[];leaks=[];errors=[];requests=[]
            def guard(route):
                req=route.request
                if any(key in req.url or key in str(req.headers) for key in keys):leaks.append('key')
                if quote('삼무공원') in req.url or '삼무공원' in req.url:leaks.append('query_in_url')
                if req.url.startswith(base+'/'):requests.append((req.method,req.url.split(base)[-1]));route.continue_()
                elif req.url.startswith('blob:'):route.continue_()
                else:external.append('external');route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/app');page.click('nav [data-screen=route]')
            for field,query in [('origin','삼무공원'),('destination','누웨마루거리')]:
                reveal(page,field);page.fill('#live-'+field+'-query',query);page.click('#live-'+field+'-search')
                page.wait_for_selector('#live-'+field+'-candidates button');page.locator('#live-'+field+'-candidates button').first.click()
                expect(page.locator('#live-'+field+'-selected')).to_contain_text('선택:')
            reveal(page,'time');page.fill('#live-date','2026-11-20');page.fill('#live-time','21:00');page.click('#live-route-button')
            page.wait_for_selector('#live-route-result .route-card',timeout=60000)
            assert '2026-11-20T21:00' in page.locator('#live-route-result').inner_text()
            assert page.locator('#live-route-result').get_by_role('button',name='지도에서 경로·시설 보기').count()==0
            expect(page.locator('#live-route-result')).to_contain_text('VWorld 배경지도 연결 완료',timeout=45000)
            page.wait_for_selector('#live-route-result .vworld-map circle title',state='attached')
            assert any(method=='POST' and path=='/maps/vworld/tile' for method,path in requests)
            assert not any('/maps/vworld/tiles/' in path for method,path in requests)
            assert not any('/research/maps/facilities' in path for method,path in requests)
            count=page.locator('#live-route-result .route-card').count()
            for width in (320,390,430):page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#live-route-result .vworld-map').screenshot(path='/tmp/jeju-selected-map.png')
            def delayed_result(route):
                time.sleep(.3);route.fulfill(status=200,json={'kind':'facility_routes'})
            page.route('**/research/routes/selected',delayed_result)
            page.evaluate("() => setTimeout(() => { const e=document.querySelector('#live-time');e.value='21:30';e.dispatchEvent(new Event('input',{bubbles:true})); },100)")
            page.click('#live-route-button');page.wait_for_timeout(600)
            assert page.locator('#live-route-result .route-card').count()==0
            page.unroute('**/research/routes/selected')
            page.route('**/maps/places/search',lambda route:route.fulfill(status=503,json={'detail':'SYNTHETIC failure'}))
            reveal(page,'origin');page.fill('#live-origin-query','SYNTHETIC 재검색');page.click('#live-origin-search');page.wait_for_selector('#live-origin-candidates .error')
            assert page.input_value('#live-origin-query')=='SYNTHETIC 재검색'
            page.unroute('**/maps/places/search')
            assert not any(key in page.content() for key in keys)
            page.click('nav [data-screen=home]');page.click('nav [data-screen=route]')
            assert page.input_value('#live-origin-query')=='' and page.input_value('#live-destination-query')==''
            assert page.locator('#live-route-result .route-card').count()==0
            page.reload();assert page.input_value('#live-origin-query')==''
            assert not external and not leaks and not errors
            browser.close()
        assert set(cache.glob('*.json'))==before
        return {'public_landmark_search':True,'selected_routes':count,'compiled_only_no_originals':True,'private_cache_files_added':0,'query_in_url':0,'keys_in_browser':0,'post_tile_requests':sum(1 for method,path in requests if method=='POST' and path=='/maps/vworld/tile'),'navigation_and_reload_cleared':True,'late_result_discarded_after_time_change':True,'search_failure_keeps_input':True,'widths':[320,390,430],'external_browser_requests':0,'javascript_errors':0}
    finally:
        if proc:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill()
if __name__=='__main__':
    result=run();Path('/tmp/jeju-selected-browser.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
