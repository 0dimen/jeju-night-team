"""검색어·키는 POST 본문으로만 전달. 검색 기록·결과 캐시를 만들지 않는다."""
import math,os,re
import httpx
from agent.maps import vworld  # 표준 HTTP 로그의 키 가림 필터 등록

class SearchUnavailable(Exception):pass


def search_places(query,mode='place'):
    if not isinstance(query,str) or not 1<=len(query.strip())<=120 or re.search(r'[\x00-\x1f]',query):raise ValueError('검색어 확인')
    if mode not in ('place','road','parcel'):raise ValueError('검색 방식 확인')
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:raise SearchUnavailable('검색 키 미설정')
    query=query.strip()
    if '제주' not in query:query='제주 '+query
    data={'service':'search','request':'search','version':'2.0','query':query,'type':'place' if mode=='place' else 'address','format':'json','size':'10','page':'1','crs':'EPSG:4326','key':key}
    if mode!='place':data['category']=mode
    try:
        with httpx.Client(timeout=12,follow_redirects=False) as client:
            with client.stream('POST','https://api.vworld.kr/req/search',data=data) as response:
                if response.status_code!=200:raise SearchUnavailable('장소 제공사 응답 확인 필요')
                raw=bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>1_000_000:raise SearchUnavailable('검색 응답 크기 초과')
        import json
        result=json.loads(raw).get('response',{})
        if result.get('status')=='NOT_FOUND':return []
        if result.get('status')!='OK':raise SearchUnavailable('장소 제공사 인증·요청 확인 필요')
        items=result.get('result',{}).get('items',[])
        if not isinstance(items,list):raise ValueError('검색 결과 형식 확인')
        candidates=[]
        for row in items[:10]:
            point=row.get('point',{});lng,lat=float(point['x']),float(point['y'])
            if not(math.isfinite(lng) and math.isfinite(lat) and 125<=lng<=128 and 32<=lat<=34):continue
            address=row.get('address',{})
            candidates.append({'name':str(row.get('title','선택한 지점'))[:200],'lng':lng,'lat':lat,
                'road_address':str(address.get('road',''))[:300],'parcel_address':str(address.get('parcel',''))[:300]})
        return candidates
    except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):raise SearchUnavailable('장소 검색 응답 형식·연결 확인 필요') from None
