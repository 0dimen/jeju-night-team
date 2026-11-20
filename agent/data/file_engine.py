"""확인된 파일의 경로·CCTV를 읽는 교체형 엔진. 데이터 채택은 별도다."""
from datetime import date
import json
from math import isfinite
from pathlib import Path
from agent.common import check_schema,stable_hash
from agent.data.routes import load_routes
from agent.geometry import covered_length

MAX_GEOMETRY_WORK=2_000_000


class FileRouteEngine:
    def __init__(self,route_path,cctv_path):
        from pyproj import Transformer
        self.route_data=load_routes(route_path)
        path=Path(cctv_path)
        if path.stat().st_size>20_000_000:raise ValueError('시설 파일 크기 확인')
        self.cctv_data=json.loads(path.read_text(encoding='utf-8'))
        self.meta=self.cctv_data.get('metadata',{})
        route_meta=self.route_data['metadata']
        self.synthetic=route_meta['synthetic']
        if not isinstance(self.meta.get('synthetic'),bool) or self.meta['synthetic']!=self.synthetic:
            raise ValueError('실제·합성 자료를 섞을 수 없습니다.')
        for meta in (route_meta,self.meta):
            for key in ('source_name','source_url','license_note','observed_at'):
                if not isinstance(meta.get(key),str) or not meta[key].strip():raise ValueError('자료 출처·이용 근거 확인')
            if not self.synthetic:
                if meta.get('rights_confirmed') is not True or meta.get('coordinate_system_confirmed') is not True:raise ValueError('실제 자료 사용 조건·좌표계 확인 필요')
                for key in ('rights_evidence','coordinate_evidence'):
                    if not isinstance(meta.get(key),str) or not meta[key].strip():raise ValueError('실제 자료 확인 근거 필요')
        if self.meta.get('coordinate_system')!='WGS84':raise ValueError('시설 좌표는 확인된 WGS84 위경도여야 합니다.')
        rows=self.cctv_data.get('rows')
        if not isinstance(rows,list) or len(rows)>100000:raise ValueError('시설 목록 확인')
        self.rows=[];ids=set()
        for row in rows:
            rid=row.get('id')
            if not isinstance(rid,str) or not rid.strip() or rid in ids:raise ValueError('시설 ID는 고유해야 합니다.')
            ids.add(rid)
            if row.get('type')!='cctv':raise ValueError('현재 파일 엔진은 CCTV만 지원합니다.')
            lat,lng=row.get('lat'),row.get('lng')
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) for x in (lat,lng)) or not(32<=lat<=34 and 125<=lng<=128):raise ValueError('제주 위경도 확인')
            date.fromisoformat(row['basis_date'])
            self.rows.append(dict(row))
        first=self.route_data['routes'][0]['coordinates'][0]
        self.project=Transformer.from_crs('EPSG:4326',f'+proj=aeqd +lat_0={first[1]} +lon_0={first[0]} +datum=WGS84 +units=m',always_xy=True)
        self.routes=[]
        for route in self.route_data['routes']:
            points=[]
            for lng,lat in route['coordinates']:
                if not(32<=lat<=34 and 125<=lng<=128):raise ValueError('현재 엔진은 제주 범위만 지원합니다.')
                x,y=self.project.transform(lng,lat,errcheck=True)
                if x*x+y*y>5000**2:raise ValueError('현재 지원 범위는 출발점 주변5km입니다.')
                points.append((x,y))
            self.routes.append({**route,'points':points})
        self.version=stable_hash([self.route_data,self.cctv_data])

    def __call__(self,request,radius=50,events=()):
        check_schema('route_request',request)
        if isinstance(radius,bool) or not isinstance(radius,(int,float)) or not isfinite(radius) or not 0<radius<=200:raise ValueError('반경은0초과200미터이하')
        points=self.route_data['routes'][0]['coordinates']
        for field,point in [('origin',points[0]),('destination',points[-1])]:
            if [request[field]['lng'],request[field]['lat']]!=point:raise ValueError('요청 위치와 파일 경로 끝점이 다릅니다.')
        inventory={r['id']:r for r in self.rows};states={};events=list(events)
        for event in events:
            check_schema('facility_change',event)
            if event['facility_id'] not in inventory or event['type']!='cctv':raise ValueError('알 수 없는 시설 변경')
            if event['after'] not in ('normal','not_working'):raise ValueError('현재 CCTV 계산은 정상·미작동 변경만 지원합니다.')
            states[event['facility_id']]=event['after']
        facilities=[]
        for row in self.rows:
            if states.get(row['id'])=='not_working':continue
            x,y=self.project.transform(row['lng'],row['lat'],errcheck=True)
            if abs(x)>5200 or abs(y)>5200:continue
            facilities.append({'x':x,'y':y})
        if sum(len(r['points'])-1 for r in self.routes)*len(facilities)>MAX_GEOMETRY_WORK:
            raise ValueError('계산 범위가 큽니다. 필요한 지역·경로로 전처리해 주세요.')
        outputs=[]
        for route in self.routes:
            near,total=covered_length(route['points'],facilities,radius)
            indicator=({'status':'historical','value':round(near/total,6),
                        'display':f'기준일이 있는 시설 위치와 경로의 인접 비율 {near/total*100:.1f}% (반경 {radius:g}m)'}
                       if self.rows else {'status':'unavailable'})
            outputs.append({'id':route['id'],'rank':1,'distance':f'{total:.1f}m','duration':f"{route['duration_minutes']:g}분",
                            'indicators':{'cctv':indicator,'streetlight':{'status':'unavailable'},'activity':{'status':'unavailable'}}})
        use_cctv='cctv' in request['preferences'] and bool(self.rows)
        outputs.sort(key=lambda r:(-r['indicators']['cctv'].get('value',0) if use_cctv else 0,float(r['duration'][:-1]),r['id']))
        for n,r in enumerate(outputs,1):r['rank']=n
        basis_dates=sorted({r['basis_date'] for r in self.rows})
        basis=(basis_dates[0] if len(basis_dates)==1 else basis_dates[0]+'~'+basis_dates[-1]) if basis_dates else self.meta['observed_at']
        sources=[{'name':self.meta['source_name']+' (시설 행별 기준일)','observed_at':basis},
                 {'name':self.route_data['metadata']['source_name'],'observed_at':self.route_data['metadata']['observed_at']}]
        limitations=['출발점 중심 평면 투영의 근사 거리이며 지형·횡단 가능성을 검증하지 않습니다.',
                     '보행 시간은 파일 제공값이며 산정 근거는 경로 파일에 있습니다.',
                     '시설 위치는 현재 작동·촬영 범위·밝기를 뜻하지 않습니다.']
        for key,label in [('attribution_url','지도 출처·라이선스'),('fix_map_url','지도 오류 수정')]:
            if self.route_data['metadata'].get(key):limitations.append(label+': '+self.route_data['metadata'][key])
        if self.synthetic:limitations.insert(0,'SYNTHETIC 합성 파일 예시이며 실제 길찾기가 아닙니다.')
        version=stable_hash([self.version,events])
        result={'run_id':('SYNTHETIC-' if self.synthetic else 'FILE-')+stable_hash([request,version,radius]),
                'data_version':version,'logic_version':f'file-aeqd-union-v1-radius-{radius:g}',
                'routes':outputs,'comparison':{'detour':'거리·시간은 경로별 값을 함께 비교하세요.',
                  'rank_reason':'CCTV 인접 비율 다음 이동 시간 순' if use_cctv else '이동 시간 순; 사용할 수 없는 시설 자료는 제외'},
                'unavailable_preferences':[p for p in request['preferences'] if p in ('streetlight','activity') or p=='cctv' and not self.rows],
                'limitations':limitations,'sources':sources}
        return check_schema('analysis_result',result)
