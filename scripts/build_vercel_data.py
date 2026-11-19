"""원본은 제외하고 공개 구간에 필요한 서버 계산 자료만 만든다."""
import json,os,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.data.research_router import ResearchRouter,ROOT,REGIONS
from agent.data.facility_route import project

FIELDS=('region','source','label','start','goal','a','b','start_gap','end_gap','lights','cctv','sources','graph')


def build(output,raw=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    raw=Path(raw or ROOT/'data/open')
    manifest=[]
    global_data={'schema_version':1,'lights':[],'cctv':{},'cctv_sources':{},'light_sources':{}}
    for region in REGIONS:
        for source in ('standard','datahub'):
            path=output/f'{region}_{source}.json'
            if raw.exists():
                r=ResearchRouter(raw,region,source)
                if source=='standard':
                    global_data['lights'].extend(r.lights)
                    global_data['light_sources'][region]=r.sources['light']
                if source not in global_data['cctv']:
                    global_data['cctv'][source]=r.cctv
                    global_data['cctv_sources'][source]=r.sources['cctv']
                # 도로 범위에서 최대 반경 200m보다 먼 시설은 계산에 영향을 주지 않는다.
                xy=[v['xy'] for v in r.graph['nodes'].values()]
                lowx=min(v[0] for v in xy)-201;highx=max(v[0] for v in xy)+201
                lowy=min(v[1] for v in xy)-201;highy=max(v[1] for v in xy)+201
                for key in ('lights','cctv'):
                    selected=[]
                    for point in getattr(r,key):
                        x,y=project(r.graph,point)
                        if lowx<=x<=highx and lowy<=y<=highy:selected.append(point)
                    setattr(r,key,selected)
                data={k:getattr(r,k) for k in FIELDS};data['schema_version']=1
                path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
            if not path.exists():raise FileNotFoundError('공개 자료나 준비된 서버 계산 자료가 필요합니다.')
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema_version')!=1 or data['region']!=region or data['source']!=source:raise ValueError('계산 자료 확인 실패')
            manifest.append({'region':region,'source':source,'bytes':path.stat().st_size,'light_points':len(data['lights']),'cctv_points':len(data['cctv'])})
    global_path=output/'jeju_facilities.json'
    if raw.exists():global_path.write_text(json.dumps(global_data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    if not global_path.is_file():raise FileNotFoundError('제주 시설 계산 자료가 필요합니다.')
    (output/'build_info.json').write_text(json.dumps({'built_at':datetime.now(timezone.utc).isoformat(),'datasets':manifest},ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'route_datasets':len(manifest),'jeju_facility_datasets':1,'bytes':sum(x['bytes'] for x in manifest)+global_path.stat().st_size,'raw_files_in_runtime':0}))
    return manifest
if __name__=='__main__':build(ROOT/'runtime/facilities')
