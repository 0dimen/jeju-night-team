"""공유 공개 파일로 도로망 경로를 찾는 연구 시연 연결. 외부 호출·원본 수정 없음."""
from collections import Counter
import csv
from functools import lru_cache
import hashlib
import io
import json
from math import isfinite
import os
from pathlib import Path
from threading import RLock

from agent.data.facility_route import build_graph,nearest_node,plan_routes,score_edges
from agent.common import load_yaml

ROOT=Path(__file__).resolve().parents[2]
REGIONS={'yeondong':('derived/jeju_city_streetlights_20241010_axisfixed.csv','삼무공원~누웨마루 공중화장실 지도 지점'),
         'seogwipo':('seogwipo_streetlights_20250725.csv','중앙로 일대~매일올레시장 지도 지점')}


def read_csv(path):
    raw=path.read_bytes()
    if len(raw)>10_000_000:raise ValueError('연구 입력 파일 크기 제한')
    text=raw.decode('utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'cp949')
    return list(csv.DictReader(io.StringIO(text))),hashlib.sha256(raw).hexdigest()


class ResearchRouter:
    def __init__(self,root,region,source):
        self.lock=RLock();self.region=region;self.source=source;root=Path(root)
        light_name,label=REGIONS[region];self.label=label
        collected=json.loads((root/'foot_routes/collection_summary.json').read_text(encoding='utf-8'))
        item=next(row for row in collected if row['start']['query']=='삼무공원') if region=='yeondong' else next(row for row in collected if row['start']['query']!='삼무공원')
        self.start,self.goal=(tuple(point) for point in item['snapped_endpoints'])
        osm=json.loads((root/'osm'/f'{region}_overpass.json').read_text(encoding='utf-8'))
        self.graph=build_graph(osm['elements'],self.start)
        if len(self.graph['nodes'])>30000 or len(self.graph['edges'])>60000:raise ValueError('연구 도로망 지원 크기 초과')
        if any(not(125<=p['lonlat'][0]<=128 and 32<=p['lonlat'][1]<=34) for p in self.graph['nodes'].values()):raise ValueError('제주 도로망 좌표 확인 필요')
        self.a,self.start_gap=nearest_node(self.graph,self.start);self.b,self.end_gap=nearest_node(self.graph,self.goal)
        if max(self.start_gap,self.end_gap)>80:raise ValueError('출발·도착과 도로망의 연결 거리가 너무 큽니다.')
        lights,light_sha=read_csv(root/light_name)
        if region=='yeondong':
            original,original_sha=read_csv(root/'jeju_city_streetlights_20241010.csv')
            note=json.loads((root/'derived/jeju_city_streetlights_20241010_axisfixed.note.json').read_text(encoding='utf-8'))
            if original_sha!=note['source_sha256'] or len(original)!=len(lights):raise ValueError('좌표 수정 원본 지문·행수 불일치')
            changed=0
            for before,after in zip(original,lights):
                if any(after.get(k)!=v for k,v in before.items() if k not in ('위도','경도')):raise ValueError('좌표 외 원본 필드가 변경됨')
                if after['위도']==before['위도'] and after['경도']==before['경도']:continue
                try:swapped=126<=float(before['위도'])<=127 and 33<=float(before['경도'])<=34.1
                except (TypeError,ValueError):swapped=False
                if not(swapped and after['위도']==before['경도'] and after['경도']==before['위도'] and after.get('좌표수정')=='위도경도교환'):raise ValueError('좌표 수정 규칙 불일치')
                changed+=1
            if changed!=note['swapped_rows']:raise ValueError('좌표 수정 행수 불일치')
        self.lights=[];held=0
        for row in lights:
            if (row.get('등종류') or row.get('종류') or '').strip() not in ('가로등','보안등'):held+=1;continue
            try:lat,lng=float(row['위도']),float(row['경도'])
            except (ValueError,TypeError):held+=1;continue
            if not(isfinite(lat) and isfinite(lng) and 32<=lat<=34 and 125<=lng<=128):held+=1;continue
            self.lights.append((lng,lat))
        cctv_name='jeju_cctv_mois_standard.csv' if source=='standard' else 'jeju_cctv_20221215.csv'
        cctv,cctv_sha=read_csv(root/cctv_name)
        required={'설치목적구분','WGS84위도','WGS84경도','데이터기준일자'} if source=='standard' else {'설치목적','위도','경도','데이터기준일'}
        if not cctv or not required<=set(cctv[0]):raise ValueError('CCTV 원본 필수 열·행 확인 필요')
        policy=load_yaml('config/cctv_selection.yaml');purposes=policy['include_purposes'];self.cctv=[];dates=Counter();purpose_counts=Counter()
        for row in cctv:
            purpose=(row.get('설치목적구분') if source=='standard' else row.get('설치목적') or '').strip()
            if purpose not in purposes:continue
            lat,lng=float(row.get('WGS84위도') if source=='standard' else row['위도']),float(row.get('WGS84경도') if source=='standard' else row['경도'])
            if not(isfinite(lat) and isfinite(lng) and 32<=lat<=34 and 125<=lng<=128):raise ValueError('선택 CCTV 좌표 확인 필요')
            self.cctv.append((lng,lat));purpose_counts[purpose]+=1
            dates[row.get('데이터기준일자') if source=='standard' else row.get('데이터기준일')]+=1
        if not self.lights or not self.cctv:raise ValueError('선택할 수 있는 시설 자료가 없습니다. 0점으로 대신하지 않습니다.')
        self.sources={'cctv':{'name':cctv_name,'sha256':cctv_sha,'source_rows':len(cctv),'selected_rows':len(self.cctv),'purposes':purposes,'purpose_rows':dict(purpose_counts),'basis_dates':dict(dates)},
            'light':{'name':light_name,'sha256':light_sha,'source_rows':len(lights),'selected_rows':len(self.lights),'held_rows':held,'basis_date':'2025-07-25' if region=='seogwipo' else '행별 기준일 없음·파일명2024-10-10'},
            'roads':{'name':'OpenStreetMap contributors','osm_base':osm.get('_collection',{}).get('osm_base'),'source_url':'https://www.openstreetmap.org/copyright','fix_map_url':'https://www.openstreetmap.org/fixthemap'}}
        self.radii=None

    def route(self,preference='both',light_radius=15,cctv_radius=50,weight=4,max_detour=1.5):
        if preference not in ('fastest','cctv','light','both'):raise ValueError('비교 기준 확인')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in (light_radius,cctv_radius,weight,max_detour)):raise ValueError('숫자 설정 확인')
        if not(0<light_radius<=80 and 0<cctv_radius<=200 and 0<=weight<=16 and 1<=max_detour<=2):raise ValueError('연구 설정 지원 범위 밖')
        lw=weight if preference in ('light','both') else 0;cw=weight if preference in ('cctv','both') else 0
        with self.lock:
            if self.radii!=(light_radius,cctv_radius):
                score_edges(self.graph,self.lights,light_radius,'light');score_edges(self.graph,self.cctv,cctv_radius,'cctv');self.radii=(light_radius,cctv_radius)
            result=plan_routes(self.graph,self.a,self.b,lw,cw,max_detour)
        rows=[]
        for name,rid,label in [('shortest','SHORTEST','최단 경로'),('facility_preferred','FACILITY','시설 조건 우선 후보')]:
            if rid=='FACILITY' and result['same_route']:continue
            route=result[name]
            rows.append({'id':rid,'label':label,'distance_m':route['length_m'],'duration_minutes':route['duration_minutes'],
                'cctv_percent':round(route['cctv_fraction']*100,2),'light_percent':round(route['light_fraction']*100,2),'coordinates':route['coordinates']})
        return {'kind':'facility_routes','synthetic':False,'research_only':True,'region':self.region,'label':self.label,
            'routes':rows,'recommended_route_id':'SHORTEST' if result['same_route'] else 'FACILITY','same_route':result['same_route'],
            'preference':preference,'parameters':{'light_radius_m':light_radius,'cctv_radius_m':cctv_radius,'requested_weight':weight,'weights_used':result['weights_used'],'max_detour':max_detour},
            'sources':self.sources,'endpoint_snap_m':[round(self.start_gap,1),round(self.end_gap,1)],
            'reason':'최단 경로와 같은 후보입니다. 다른 길을 억지로 만들지 않습니다.' if result['same_route'] else '시설 인접 구간의 탐색 비용을 낮춰 찾은 후보입니다. 각 인접 비율과 우회 거리를 비교하세요.',
            'limitations':['공개 자료를 사용한 연구 시연입니다. 안전·밝기·작동·촬영 범위를 보장하지 않습니다.','예상 시간은 거리÷분당75m(시속4.5km) 가정입니다. 신호·경사·계단·폐쇄를 실측하지 않았습니다.','가장 가까운 도로 노드에 연결하며 요청 끝점과 차이는 별도로 표시합니다.','가중치·조명 반경·우회 한도는 연구 설정이며 사용자 시험으로 확정한 값이 아닙니다.','현재 공개 구간 두 곳만 지원합니다. 집이나 임의 지점의 길찾기가 아닙니다.','인접 비율은 공개 목록 기준입니다. 0%여도 실제 시설이 없다는 뜻은 아닙니다.','자료 목적·수록 범위가 달라 서로 다른 지역의 안전 수준을 비교하지 않습니다.','https://www.openstreetmap.org/copyright · https://www.openstreetmap.org/fixthemap']}


def get_router(region,source='standard'):
    root=Path(os.environ.get('JEJU_OPEN_DATA_DIR',str(ROOT/'data/open')))
    files=[root/'foot_routes/collection_summary.json',root/'osm'/f'{region}_overpass.json',root/REGIONS[region][0],root/('jeju_cctv_mois_standard.csv' if source=='standard' else 'jeju_cctv_20221215.csv'),ROOT/'config/cctv_selection.yaml']
    if region=='yeondong':files.extend([root/'jeju_city_streetlights_20241010.csv',root/'derived/jeju_city_streetlights_20241010_axisfixed.note.json'])
    version=tuple((p.stat().st_mtime_ns,p.stat().st_size) for p in files)
    return _cached(str(root),region,source,version)


@lru_cache(maxsize=2)
def _cached(root,region,source,version):return ResearchRouter(root,region,source)
