"""CCTV 원본의 기본 품질만 점검한다. 지표 채택·사전·경로 엔진을 바꾸지 않는다."""
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime
import hashlib
import io
import json
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo


def audit(path,as_of=None):
    path=Path(path);content=path.read_bytes()
    if len(content)>20_000_000:raise ValueError('20MB보다 큰 원본은 별도 전처리로 점검해야 합니다.')
    for encoding in ('utf-8-sig','cp949'):
        try:text=content.decode(encoding);break
        except UnicodeError:continue
    else:raise ValueError('UTF-8 또는 CP949 CSV를 확인해야 합니다.')
    reader=csv.DictReader(io.StringIO(text));rows=list(reader)
    if not {'위도','경도','데이터기준일'}<=set(reader.fieldnames or []):
        raise ValueError('좌표·기준일 칸이 없습니다.')
    as_of=as_of or datetime.now(ZoneInfo('Asia/Seoul')).date()
    dates=Counter();purposes=Counter();positions=defaultdict(list)
    invalid_dates=invalid_coordinates=outside=invalid_counts=0
    camera_total=0
    for line,row in enumerate(rows,2):
        purposes[(row.get('설치목적') or '').strip() or '미기재']+=1
        raw=(row.get('데이터기준일') or '').strip()
        try:
            date=datetime.strptime(raw,'%Y%m%d' if len(raw)==8 else '%Y-%m-%d').date()
            if date>as_of:raise ValueError('미래 기준일')
            dates[date.isoformat()]+=1
        except ValueError:invalid_dates+=1
        try:
            lat,lng=float(row['위도']),float(row['경도'])
            if not(isfinite(lat) and isfinite(lng) and -90<=lat<=90 and -180<=lng<=180):
                raise ValueError('잘못된 좌표')
            positions[(lat,lng)].append(line)
            outside+=not(32<=lat<=34 and 125<=lng<=128)
        except (ValueError,TypeError):invalid_coordinates+=1
        try:
            count=int(row.get('카메라대수',''))
            if count<0:raise ValueError('음수 대수')
            camera_total+=count
        except (ValueError,TypeError):invalid_counts+=1
    earliest=min(dates,default=None);latest=max(dates,default=None)
    duplicate_groups=[lines for lines in positions.values() if len(lines)>1]
    result={'checked_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
        'source_path':str(path),'sha256':hashlib.sha256(content).hexdigest(),
        'bytes':len(content),'encoding':encoding,'rows':len(rows),'columns':reader.fieldnames,
        'status':'candidate_only','adopted':False,'as_of':as_of.isoformat(),
        'basis_date_counts':dict(sorted(dates.items())),
        'invalid_or_missing_basis_dates':invalid_dates,'oldest_basis_date':earliest,'latest_basis_date':latest,
        'latest_age_days':(as_of-datetime.strptime(latest,'%Y-%m-%d').date()).days if latest else None,
        'valid_global_coordinates':sum(len(v) for v in positions.values()),
        'invalid_or_missing_coordinates':invalid_coordinates,
        'outside_coarse_jeju_box':outside,
        'box_definition':'위도32~34·경도125~128의 거친 사각 범위. 행정 경계나 주소 일치를 검증한 것은 아님.',
        'unique_coordinate_pairs':len(positions),
        'extra_rows_at_repeated_coordinates':sum(len(v)-1 for v in duplicate_groups),
        'duplicate_coordinate_groups':len(duplicate_groups),
        'example_duplicate_row_numbers':duplicate_groups[:5],
        'purpose_counts':dict(sorted(purposes.items())),
        'declared_camera_count':({'status':'available','value':camera_total}
                                 if rows and not invalid_counts else {'status':'unavailable'}),
        'invalid_or_missing_camera_counts':invalid_counts,
        'rights_confirmed':False,'designated_eligibility_confirmed':False,'coordinate_system_confirmed':False,
        'limitations':['표의 기재 대수이며 현재 작동하는 기기의 실측 개수가 아님',
            '좌표 중복이 곧 같은 시설을 뜻하지 않으므로 자동 병합하지 않음',
            '설치 목적별 경로 비교 적합성은 사람이 검토해야 함',
            '과거 기준일의 위치 자료이며 현재 설치·작동·촬영 범위를 확인하지 않음',
            '원본 확보·기본 품질 검사는 실제 엔진 연결·이용 조건·대회 요건 충족과 별개']}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='data/raw/PUBLIC_jeju_cctv_source.csv')
    parser.add_argument('--out',default='data/processed/cctv_source_audit.json')
    args=parser.parse_args();result=audit(args.source)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
