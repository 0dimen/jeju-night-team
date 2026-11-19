"""서버 키로 제주 타일만 요청. 키·제공사 오류 본문·URL을 반환하지 않는다."""
import math,os,time,logging,re
from threading import BoundedSemaphore,Lock
from collections import deque
import httpx

class RedactMapKey(logging.Filter):
    def filter(self,record):
        key=os.environ.get('VWORLD_API_KEY','').strip()
        if key:
            record.msg=record.getMessage().replace(key,'[REDACTED]')
            record.args=()
        record.msg=re.sub(r'https://api\.vworld\.kr/req/wmts/\S+','https://api.vworld.kr/req/wmts/[REDACTED]',record.getMessage())
        record.args=()
        return True


# 표준 HTTP 라이브러리의 정보·디버그 로그에서도 서버 키를 가린다.
for _name in ('httpx','httpcore.http11','httpcore.http2','httpcore.connection','httpcore.proxy'):
    logging.getLogger(_name).addFilter(RedactMapKey())


class MapUnavailable(Exception):pass
_gate=BoundedSemaphore(2)
_lock=Lock()
_requests=deque()
_blocked_until=0.0


def validate_tile(z,x,y):
    if not all(type(v) is int for v in (z,x,y)) or not 10<=z<=19 or not(0<=x<2**z and 0<=y<2**z):raise ValueError('타일 범위 확인')
    n=2**z
    west=x/n*360-180;east=(x+1)/n*360-180
    north=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
    south=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+1)/n))))
    if east<125 or west>128 or north<32 or south>34:raise ValueError('제주 연구 지도 범위 밖')


def fetch_tile(z,x,y):
    global _blocked_until
    validate_tile(z,x,y)
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:raise MapUnavailable('지도 키 미설정')
    # 제공사 실제 한도를 대신하는 값이 아니라 로컬 중계의 호출 폭주 방지 한도다.
    with _lock:
        now=time.monotonic()
        while _requests and _requests[0]<now-60:_requests.popleft()
        if now<_blocked_until or len(_requests)>=120:raise MapUnavailable('잠시 후 지도 다시 요청')
        _requests.append(now)
    if not _gate.acquire(timeout=10):raise MapUnavailable('지도 요청 처리 중')
    try:
        try:
            # 도메인은 키 발급 조건에 맞춰 운영자가 별도 설정한다. 요청 헤더에서 추측하지 않는다.
            domain=os.environ.get('VWORLD_DOMAIN','').strip()
            headers={'Referer':domain} if domain.startswith(('https://','http://')) and '\n' not in domain and '\r' not in domain else {}
            with httpx.Client(timeout=10,follow_redirects=False) as client:
                with client.stream('GET',f'https://api.vworld.kr/req/wmts/1.0.0/{key}/Base/{z}/{y}/{x}.png',headers=headers) as response:
                    if response.status_code!=200:
                        if response.status_code in (401,403,429):
                            with _lock:_blocked_until=time.monotonic()+60
                        raise MapUnavailable('지도 제공사 응답 확인 필요')
                    content=bytearray()
                    for part in response.iter_bytes():
                        content.extend(part)
                        if len(content)>1_000_000:raise MapUnavailable('지도 응답 크기 초과')
            if not content.startswith(b'\x89PNG\r\n\x1a\n'):raise MapUnavailable('지도 이미지 응답 아님')
            return bytes(content)
        except (httpx.HTTPError,ValueError) as exc:
            raise MapUnavailable('지도 제공사 연결 실패') from None
    finally:_gate.release()


def public_points(router,routes):
    from agent.data.facility_route import project
    points=[project(router.graph,p) for row in routes for p in row['coordinates']]
    minx=min(p[0] for p in points)-100;maxx=max(p[0] for p in points)+100
    miny=min(p[1] for p in points)-100;maxy=max(p[1] for p in points)+100
    result=[];counts={}
    for kind,coordinates in (('cctv',router.cctv),('light',router.lights)):
        found=[]
        for coord in coordinates:
            x,y=project(router.graph,coord)
            if minx<=x<=maxx and miny<=y<=maxy:found.append(list(coord))
        counts[kind]=len(found)
        result.extend({'kind':kind,'coordinates':coord} for coord in found[:2000])
    return {'points':result,'counts_in_route_box':counts,'truncated':any(n>2000 for n in counts.values()),
            'notice':'경로 주변 약 100m 사각 범위의 공개 목록 위치입니다. 촬영 범위·작동·밝기·현장 통행을 확인한 것이 아닙니다.'}
