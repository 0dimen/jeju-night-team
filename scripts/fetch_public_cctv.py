"""환경변수의 인증키로 기관별 수집. 원본·출력 폴더는 Git밖에 두세요."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.data.cctv_api import fetch_page,decode_page,CCTVAPIError


def collect(agency,output,max_pages=30):
    rows=[];total=None;seen=set();page_counts=[]
    for page in range(1,max_pages+1):
        path=output/f'agency_{agency}_page_{page}.json'
        if path.exists():data=json.loads(path.read_text(encoding='utf-8'))
        else:
            time.sleep(1)
            data=fetch_page(agency,page)
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        part,current=decode_page(data,agency,page)
        if total is not None and total!=current:raise CCTVAPIError('수집 도중 전체 행수가 바뀌었습니다. 새 폴더에서 다시 확인하세요.')
        total=current
        for row in part:
            if row['MNG_NO'] in seen:raise CCTVAPIError('페이지 간 중복 관리번호가 있습니다.')
            seen.add(row['MNG_NO'])
        rows.extend(part);page_counts.append(len(part))
        if len(rows)==total:return rows,{'provider_total':total,'pages':len(page_counts),'page_counts':page_counts}
        if not part or len(rows)>total:raise CCTVAPIError('전체 페이지를 확인하지 못했습니다.')
    raise CCTVAPIError('최대 페이지 제한에 도달했습니다. 부분 결과를 완료로 처리하지 않습니다.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--agency',action='append',required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    try:
        rows=[];scopes={}
        for agency in dict.fromkeys(args.agency):
            values,scope=collect(agency,args.output);rows.extend(values);scopes[agency]=scope
        summary={'scopes':scopes,'rows':len(rows),'purpose_rows':dict(Counter(row['INSTL_PRPS_SE_NM'] for row in rows)),
            'operationally_adopted':False,'scope':'명시한 기관의 전체 페이지. 제주 모든 시설을 포괄한다는 뜻 아님'}
        (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False,indent=2))
    except (CCTVAPIError,ValueError,OSError):
        print('수집을 완료하지 못했습니다. 인증·응답 형식·기관·페이지 상태를 확인하세요.',file=sys.stderr);sys.exit(1)
