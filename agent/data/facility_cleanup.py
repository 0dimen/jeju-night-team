"""공개 시설 CSV 연구용 정리. 원본 보존, 좌표 자동 수정·자료 채택 없음."""
from collections import Counter
import csv
from datetime import date
import hashlib
import io
from math import isfinite
from pathlib import Path


def prepare_facilities(path, *, source_name, source_url, kind, encoding='utf-8-sig', include_purposes=None):
    if kind not in ('cctv','light'):raise ValueError('시설 종류 확인')
    if kind=='cctv' and not include_purposes:raise ValueError('CCTV 목적 선택을 명시하세요.')
    if not source_name.strip() or not source_url.startswith('https://'):raise ValueError('출처 확인')
    raw=Path(path).read_bytes()
    reader=csv.DictReader(io.StringIO(raw.decode(encoding)))
    if not reader.fieldnames or not {'위도','경도'} <= set(reader.fieldnames):raise ValueError('위도·경도 열 필요')
    rows=[];rejected=[];reasons=Counter();positions=Counter();total=0
    for line,row in enumerate(reader,2):
        total+=1
        facility_kind=(row.get('등종류') or row.get('종류') or '').strip()
        reason=None
        if kind=='cctv' and (row.get('설치목적') or '').strip() not in include_purposes:reason='선택하지 않은 설치 목적'
        elif kind=='light' and facility_kind not in ('가로등','보안등'):reason='미기재·지원하지 않는 시설 종류'
        lat_text=(row.get('위도') or '').strip();lng_text=(row.get('경도') or '').strip()
        if not reason:
            if not lat_text or not lng_text:reason='좌표 빈칸'
            else:
                try:
                    lat,lng=float(lat_text),float(lng_text)
                    if not(isfinite(lat) and isfinite(lng)):reason='유한 숫자가 아닌 좌표'
                    elif 125<=lat<=128 and 32<=lng<=34:reason='좌표 축 교환 의심·수정 보류'
                    elif not(32<=lat<=34 and 125<=lng<=128):reason='제주 거친 범위 밖 좌표'
                except ValueError:reason='좌표 숫자 오류'
        if reason:
            reasons[reason]+=1;rejected.append({'source_line':line,'reason':reason});continue
        basis=(row.get('데이터기준일') or '').strip()
        if len(basis)==8 and basis.isdigit():basis=f'{basis[:4]}-{basis[4:6]}-{basis[6:]}'
        date_issue=False
        if basis:
            try:date.fromisoformat(basis)
            except ValueError:basis=None;date_issue=True
        else:basis=None
        positions[(lat,lng)]+=1
        rows.append({'id':f'{kind}-{line}','type':kind,'source_line':line,'lat':lat,'lng':lng,
                     'kind':facility_kind if kind=='light' else 'cctv','purpose':row.get('설치목적') if kind=='cctv' else None,
                     'basis_date':basis,'basis_date_invalid':date_issue})
    for row in rows:row['same_coordinate_row_count']=positions[(row['lat'],row['lng'])]
    summary={'source_rows':total,'candidate_rows':len(rows),'held_rows':len(rejected),'held_reason_counts':dict(reasons),
             'basis_dates':dict(Counter(row['basis_date'] or '행별 기준일 없음' for row in rows)),
             'duplicate_coordinate_extra_rows':sum(n-1 for n in positions.values()),'automatic_axis_corrections':0,'automatic_merges':0}
    return {'metadata':{'synthetic':False,'source_name':source_name,'source_url':source_url,
             'source_sha256':hashlib.sha256(raw).hexdigest(),'coordinate_assumption':'위도·경도 열 그대로. 범위 검사는 좌표계 검증이 아님',
             'rights_confirmed':False,'coordinate_system_confirmed':False,'operationally_adopted':False,
             'scope':'연구용 정리 후보. 점등·작동·현장·안전 상태 미확인'},'summary':summary,'rows':rows,'held_rows':rejected}
