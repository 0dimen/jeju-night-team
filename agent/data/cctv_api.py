"""공식 CCTV API의 수동 수집 연결. 서버 기본 추천에는 자동 적용하지 않는다."""
import json
import os
import re
import urllib.parse
import urllib.request

ENDPOINT='https://apis.data.go.kr/1741000/cctv_info/info'


class CCTVAPIError(ValueError):
    pass


def decode_page(data,agency,page):
    try:
        response=data['response'];header=response['header'];body=response['body']
        if str(header['resultCode']) not in ('0','00'):raise CCTVAPIError('제공자가 조회를 거부했습니다. 활용 신청·인증 상태를 확인하세요.')
        total=body['totalCount'];number=body['pageNo']
        if isinstance(total,bool) or not isinstance(total,int) or total<0 or int(number)!=page:raise ValueError()
        items=body.get('items') or {};rows=items.get('item',[]) if isinstance(items,dict) else items
        if isinstance(rows,dict):rows=[rows]
        if rows is None:rows=[]
        if not isinstance(rows,list) or len(rows)>100 or len(rows)>total:raise ValueError()
        if any(not isinstance(row,dict) or str(row.get('OPN_ATMY_GRP_CD'))!=agency or not row.get('MNG_NO') for row in rows):raise ValueError()
        ids=[str(row['MNG_NO']) for row in rows]
        if len(ids)!=len(set(ids)):raise ValueError()
        return rows,total
    except CCTVAPIError:raise
    except Exception:raise CCTVAPIError('기관·페이지·개수 또는 응답 형식을 확인하지 못했습니다.') from None


def fetch_page(agency,page,key=None,opener=urllib.request.urlopen):
    if not isinstance(agency,str) or not re.fullmatch(r'\d{7}',agency) or isinstance(page,bool) or not isinstance(page,int) or page<1:
        raise CCTVAPIError('기관 코드와 페이지를 확인하세요.')
    key=(key if key is not None else os.environ.get('DATA_GO_KR_SERVICE_KEY','')).strip()
    if not key:raise CCTVAPIError('DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.')
    args={'serviceKey':key,'returnType':'json','pageNo':page,'numOfRows':100,'cond[OPN_ATMY_GRP_CD::EQ]':agency}
    request=urllib.request.Request(ENDPOINT+'?'+urllib.parse.urlencode(args),headers={'User-Agent':'jeju-night-research/1.0'})
    try:
        with opener(request,timeout=30) as response:
            if response.status!=200:raise ValueError()
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError()
        text=raw.decode('utf-8-sig')
        for token in {key,urllib.parse.quote(key,safe=''),urllib.parse.quote_plus(key)}:
            if token:text=text.replace(token,'[REDACTED]')
        data=json.loads(text)
    except Exception:raise CCTVAPIError('조회에 실패했습니다. 연결·인증·호출 한도를 확인하세요.') from None
    decode_page(data,agency,page)
    return data
