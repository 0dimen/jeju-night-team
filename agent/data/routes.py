"""GeoJSON 보행 경로 입력 검사. 길을 생성하거나 실제 보행 가능 여부를 추측하지 않는다."""
from datetime import datetime
import hashlib
import json
from math import asin,cos,isfinite,radians,sin,sqrt
from pathlib import Path


def segment_distance(a,b):
    lon1,lat1,lon2,lat2=map(radians,(*a,*b))
    h=sin((lat2-lat1)/2)**2+cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return 6371000*2*asin(min(1,sqrt(max(0,h))))


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value)


def load_routes(path):
    raw=Path(path).read_bytes()
    if len(raw)>5_000_000:raise ValueError('경로 파일은 5MB 이하여야 합니다.')
    data=json.loads(raw.decode('utf-8-sig'))
    if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list):
        raise ValueError('GeoJSON FeatureCollection이 필요합니다.')
    # GeoJSON 좌표는 경도, 위도 순서다. 투영 좌표를 자동 변환하지 않는다.
    if 'crs' in data:raise ValueError('별도 좌표계 지정 대신 WGS84 경도·위도 파일을 준비하세요.')
    meta=data.get('properties',{})
    for key in ('source_name','source_url','license_note','observed_at'):
        if not isinstance(meta.get(key),str) or not meta[key].strip():raise ValueError(key+' 출처 정보가 필요합니다.')
    datetime.fromisoformat(meta['observed_at'])
    if not isinstance(meta.get('synthetic'),bool):raise ValueError('합성 여부를 명시해야 합니다.')
    features=data['features']
    if not 2<=len(features)<=20:raise ValueError('같은 구간을 비교할 경로 2~20개가 필요합니다.')
    routes=[];ids=set()
    for feature in features:
        if feature.get('type')!='Feature':raise ValueError('Feature 형식을 확인하세요.')
        props=feature.get('properties',{});geom=feature.get('geometry',{})
        rid=props.get('id')
        if not isinstance(rid,str) or not rid.strip() or rid in ids:raise ValueError('경로 이름은 비어 있지 않고 고유해야 합니다.')
        ids.add(rid)
        if geom.get('type')!='LineString':raise ValueError('경로는 LineString이어야 합니다.')
        points=geom.get('coordinates')
        if not isinstance(points,list) or not 2<=len(points)<=50000:raise ValueError('경로 점은 2~50000개여야 합니다.')
        for point in points:
            if not isinstance(point,list) or len(point)!=2 or not all(number(x) for x in point):raise ValueError('좌표는 경도·위도 두 숫자여야 합니다.')
            if not(-180<=point[0]<=180 and -90<=point[1]<=90):raise ValueError('위경도 범위를 확인하세요.')
        length=sum(segment_distance(a,b) for a,b in zip(points,points[1:]))
        if length<=0:raise ValueError('길이가 없는 경로는 사용할 수 없습니다.')
        minutes=props.get('duration_minutes')
        if not number(minutes) or minutes<=0:raise ValueError('보행 시간은 근거와 함께 양수로 제공해야 합니다.')
        if not isinstance(props.get('duration_basis'),str) or not props['duration_basis'].strip():raise ValueError('보행 시간 산정 근거가 필요합니다.')
        if props.get('walkability_checked') is not True:raise ValueError('보행 가능 여부 확인이 필요합니다.')
        routes.append({'id':rid,'coordinates':points,'length_m':round(length,3),'duration_minutes':minutes,
                       'duration_basis':props['duration_basis']})
    # 같은 출발·도착 좌표를 요구한다. 허용 오차를 임의 운영 기준으로 정하지 않는다.
    if any(r['coordinates'][0]!=routes[0]['coordinates'][0] or r['coordinates'][-1]!=routes[0]['coordinates'][-1] for r in routes[1:]):
        raise ValueError('비교 경로의 출발점과 도착점은 같아야 합니다.')
    return {'source_sha256':hashlib.sha256(raw).hexdigest(),'metadata':meta,'routes':routes,
            'scope':'입력 형식·출처·좌표·거리 계산 점검. 외부의 보행 확인 표시는 별도 실측 검증이 아님'}
