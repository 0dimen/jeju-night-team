"""목적 선택 설정에 따라 원본을 보존한 채 CCTV 행을 고른다."""
import csv
from datetime import datetime
import hashlib
import io
from math import isfinite
from pathlib import Path
import yaml


def select(source,policy_path):
    content=Path(source).read_bytes()
    policy_bytes=Path(policy_path).read_bytes()
    policy=yaml.safe_load(policy_bytes.decode('utf-8'))
    purposes=policy.get('include_purposes')
    if not isinstance(purposes,list) or not purposes or not all(isinstance(p,str) and p.strip() for p in purposes):
        raise ValueError('포함할 설치 목적 목록이 필요합니다.')
    for encoding in ('utf-8-sig','cp949'):
        try:text=content.decode(encoding);break
        except UnicodeError:continue
    else:raise ValueError('원본 문자 형식을 확인하세요.')
    rows=list(csv.DictReader(io.StringIO(text)));selected=[];excluded={}
    for line,row in enumerate(rows,2):
        purpose=(row.get('설치목적') or '').strip()
        if purpose not in purposes:
            excluded[purpose]=excluded.get(purpose,0)+1;continue
        lat,lng=float(row['위도']),float(row['경도'])
        if not(isfinite(lat) and isfinite(lng) and -90<=lat<=90 and -180<=lng<=180):
            raise ValueError(f'{line}행 좌표 오류')
        raw=row['데이터기준일'].strip()
        date=datetime.strptime(raw,'%Y%m%d' if len(raw)==8 else '%Y-%m-%d').date().isoformat()
        selected.append({'source_line':line,'purpose':purpose,'lat':lat,'lng':lng,
                         'basis_date':date,'declared_camera_count':int(row['카메라대수']),
                         'road_address':row.get('도로명주소',''),'parcel_address':row.get('지번주소','')})
    # 명시적으로 True인 경우만 허용한다. 문자열 'false'는 승인으로 처리하지 않는다.
    ready=policy.get('rights_confirmed') is True and policy.get('coordinate_system_confirmed') is True
    return {'policy_version':policy['version'],'policy_sha256':hashlib.sha256(policy_bytes).hexdigest(),
            'source_sha256':hashlib.sha256(content).hexdigest(),'source_rows':len(rows),
            'include_purposes':purposes,'excluded_purpose_counts':excluded,
            'ready_for_real_route_use':ready,'rows':selected}
