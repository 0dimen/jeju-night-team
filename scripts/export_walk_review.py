"""현재 추천 형상별 빈 지도 검토표. 기존 표를 덮어쓰지 않는다."""
import argparse,csv,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.data.research_router import get_router

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region',choices=['yeondong','seogwipo'],required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    routes=get_router(args.region).route()['routes']
    with open(args.output,'x',encoding='utf-8-sig',newline='') as f:
        fields=['region','route_id','segment_id','osm_way','coordinates','map_url','map_tags','status','checked_at','image_date','evidence','reviewer']
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        import json
        for route in routes:
            for s in route['walk_review']['segments']:
                w.writerow({'region':args.region,'route_id':route['id'],**{k:s[k] for k in ('segment_id','osm_way','map_url')},'coordinates':json.dumps(s['coordinates']),'map_tags':json.dumps(s['map_tags'],ensure_ascii=False),'status':'미확인'})
if __name__=='__main__':main()
