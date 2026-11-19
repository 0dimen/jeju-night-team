import asyncio,json,socket,subprocess,sys
from urllib.request import urlopen
from playwright.async_api import async_playwright

async def main():
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 base=f'http://127.0.0.1:{port}'
 proc=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(60):
   try:
    with urlopen(base+'/health',timeout=.2):break
   except OSError:await asyncio.sleep(.1)
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage']);checks=[]
   for width in (390,768,1280):
    page=await browser.new_page(viewport={'width':width,'height':844});errors=[];outside=[];calls=[];mode='normal'
    page.on('pageerror',lambda e:errors.append(str(e)))
    async def guard(route):
     url=route.request.url
     if not url.startswith(base):outside.append(url);await route.abort();return
     if url==base+'/research/maps/facilities':
      region=route.request.post_data_json['region'];calls.append(region);request_mode=mode
      if region=='yeondong':await asyncio.sleep(.4)
      if request_mode=='error':await route.fulfill(status=503,body='{}');return
      kinds=['cctv','cctv','light'] if region=='seogwipo' else ['cctv','light','light']
      points=[] if request_mode=='empty' else [{'kind':kind,'coordinates':[126.49+i*.0001,33.49+i*.0001]} for i,kind in enumerate(kinds)]
      try:await route.fulfill(status=200,content_type='application/json',body=json.dumps({'points':points,'notice':'합성 시설 검사'}))
      except Exception:pass
     else:await route.continue_()
    await page.route('**/*',guard)
    await page.goto(base+'/app')
    # 다른 화면의 실제 지역 비교 선택은 시설 조회 선택에 전달되지 않아야 한다.
    await page.locator('nav button[data-screen="data"]').click();await page.locator('button[data-screen="region"]:visible').click()
    await page.wait_for_function('document.querySelectorAll("#region-choices input").length > 2')
    for name in ('대륜동','애월읍'):await page.locator('#region-choices label').filter(has_text=name).click()
    await page.locator('nav button[data-screen="home"]').click();await page.locator('button[data-screen="facility"]:visible').click()
    assert await page.locator('#facility-region').input_value()==''
    assert await page.locator('#facility-region-open').is_disabled() and calls==[], (await page.locator('#facility-region-open').is_disabled(),calls)
    await page.screenshot(path=f'/tmp/jeju-facility-select-{width}.png')
    async def choose(region):
     await page.locator('#facility-region').select_option(region);await page.locator('#facility-region-open').click()
    async def change():await page.locator('#facility [data-view-go="select"]:visible').first.click()
    await choose('seogwipo')
    await page.locator('#facility-cctv-note').get_by_text('공개 목록 위치 2곳',exact=False).wait_for()
    await page.locator('#facility-layers input[value="light"]').locator('..').click()
    assert '1곳' in await page.locator('#facility-light-note').inner_text()
    assert '서귀포' in await page.locator('#facility-scope').inner_text()
    await page.screenshot(path=f'/tmp/jeju-facility-selected-{width}.png')
    await page.locator('#facility [data-view-go="nearby"]:visible').click()
    assert '2곳' in await page.locator('#nearby-cctv').inner_text() and len(calls)==1
    await page.locator('#screen-back').click();await change()
    await choose('yeondong');await page.locator('#screen-back').click()
    await choose('seogwipo')
    await page.locator('#facility-cctv-note').get_by_text('공개 목록 위치 2곳',exact=False).wait_for();await page.wait_for_timeout(600)
    assert '2곳' in await page.locator('#facility-cctv-note').inner_text() and '서귀포' in await page.locator('#facility-scope').inner_text()
    mode='error';await change();await choose('yeondong')
    await page.locator('#facility-map').get_by_text('선택 구역의 시설 자료를 불러오지 못했어요.',exact=False).wait_for()
    assert '불러오지 못함' in await page.locator('#facility-cctv-note').inner_text()
    assert await page.locator('#facility-map .fac-cctv').count()==0
    mode='empty';await change();await choose('seogwipo')
    await page.locator('#facility-cctv-note').get_by_text('공개 목록 위치 0곳',exact=False).wait_for()
    assert '0곳' in await page.locator('#nearby-cctv').text_content()
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth') and not errors and not outside,(errors,outside)
    checks.append({'width':width,'independent_selection':True,'race_discarded':True,'failed_no_fallback':True,'empty_no_stale_count':True,'errors':0,'external':0})
    await page.close()
   await browser.close();print(json.dumps(checks))
 finally:proc.terminate();proc.wait(timeout=5)
asyncio.run(main())
