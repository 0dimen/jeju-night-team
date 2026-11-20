"""현재 계산 결과를 비교표로 표시한다. 안전 점수·새 가중치를 만들지 않는다."""
from agent.common import check_schema


def comparison_table(analysis):
    check_schema('analysis_result',analysis)
    rows=[]
    for route in analysis['routes']:
        cctv=route['indicators']['cctv']
        value=cctv.get('value') if cctv['status'] in ('verified','confirmed','historical') else None
        rows.append({'id':route['id'],'rank':route['rank'],'distance':route['distance'],
                     'duration':route['duration'],'cctv_comparison_value':round(value*100,1) if value is not None else None,
                     'cctv_status':cctv['status']})
    usable=[r for r in rows if r['cctv_comparison_value'] is not None]
    return {'rows':rows,'recommended_route_id':min(rows,key=lambda r:r['rank'])['id'] if rows else None,
            'fastest_route_id':min(rows,key=lambda r:(float(r['duration'][:-1]),r['id']))['id'] if rows else None,
            'facility_leader_route_id':max(usable,key=lambda r:r['cctv_comparison_value'])['id'] if usable else None,
            'rank_reason':analysis['comparison']['rank_reason'],
            'tradeoff':analysis['comparison']['detour'],
            'sources':analysis['sources'],'limitations':analysis['limitations'],
            'value_meaning':'CCTV 인접 구간 비율 × 100. 안전 확률·작동·촬영 범위가 아님'}
