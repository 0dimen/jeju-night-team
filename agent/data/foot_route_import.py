"""수집해 둔 보행 응답을 후보 경로 파일로 정리한다. 온라인 요청은 하지 않는다."""
from datetime import datetime
import hashlib
import json
from math import isfinite


def prepare_foot_candidates(responses,observed_at,profile='routed-foot'):
    if profile!='routed-foot':raise ValueError('보행 프로필 출처 확인 필요')
    datetime.fromisoformat(observed_at)
    features=[];seen=set();endpoints=None
    for response in responses:
        if response.get('code')!='Ok':raise ValueError('경로 제공 응답 실패')
        for route in response.get('routes',[]):
            geometry=route.get('geometry',{})
            if geometry.get('type')!='LineString':raise ValueError('선형 경로 확인')
            points=geometry.get('coordinates')
            if not isinstance(points,list) or len(points)<2:raise ValueError('경로 점 부족')
            for point in points:
                if not isinstance(point,list) or len(point)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) for x in point):raise ValueError('위경도 숫자 확인')
                if not(-180<=point[0]<=180 and -90<=point[1]<=90):raise ValueError('위경도 범위 확인')
            current=[points[0],points[-1]]
            if endpoints is not None and endpoints!=current:raise ValueError('비교할 출발·도착점이 다름')
            endpoints=current
            modes=[step.get('mode') for leg in route.get('legs',[]) for step in leg.get('steps',[])]
            if not modes or any(mode!='walking' for mode in modes):raise ValueError('반환된 이동수단이 보행인지 확인 필요')
            duration=route.get('duration');distance=route.get('distance')
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) or x<=0 for x in (duration,distance)):raise ValueError('제공 거리·시간 확인')
            fingerprint=hashlib.sha256(json.dumps(points).encode()).hexdigest()
            if fingerprint in seen:continue
            seen.add(fingerprint)
            features.append({'type':'Feature','properties':{'id':f'R{len(features)+1}',
                'duration_minutes':duration/60,'duration_basis':'FOSSGIS OSRM routed-foot 제공 추정값, 현장 실측 아님',
                'provider_distance_m':distance,'walkability_checked':True,
                'walkability_check_basis':'보행 전용 프로필 및 모든 단계 mode=walking 확인. 지도상 정보만 확인',
                'onsite_checked':False},'geometry':geometry})
    if len(features)<2:raise ValueError('동일 구간의 서로 다른 후보 경로2개가 필요합니다.')
    return {'type':'FeatureCollection','properties':{'synthetic':False,
        'source_name':'OpenStreetMap contributors / FOSSGIS OSRM 보행 경로',
        'source_url':'https://routing.openstreetmap.de/about.html','observed_at':observed_at,
        'license_note':'© OpenStreetMap contributors, ODbL1.0; FOSSGIS서비스 조건 별도. 공개 서비스 채택 전 확인',
        'attribution_url':'https://www.openstreetmap.org/copyright',
        'fix_map_url':'https://www.openstreetmap.org/fixthemap',
        'rights_confirmed':False,'coordinate_system_confirmed':True,
        'coordinate_evidence':'제공 GeoJSON 경도·위도 및 범위 확인. RFC7946',
        'operationally_adopted':False,'onsite_checked':False},'features':features}
