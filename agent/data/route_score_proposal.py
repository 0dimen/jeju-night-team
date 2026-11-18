"""별도 연구용 점수 비교. 기본 에이전트·운영 추천 설정을 변경하지 않는다."""
from math import isfinite


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value)


def compare_proposals(routes,profiles):
    if not isinstance(routes,list) or not 3<=len(routes)<=20:raise ValueError('서로 다른 입력 후보3~20개 필요')
    ids=set()
    for route in routes:
        if not isinstance(route.get('id'),str) or not route['id'].strip() or route['id'] in ids:raise ValueError('고유 경로ID 필요')
        ids.add(route['id'])
        if not finite(route.get('minutes')) or route['minutes']<=0:raise ValueError('양수 예상 시간 필요')
        for field in ('cctv_fraction','light_fraction'):
            if not finite(route.get(field)) or not 0<=route[field]<=1:raise ValueError('시설 비율 결측·범위 확인: '+field)
    if not isinstance(profiles,dict) or len(profiles)!=3:raise ValueError('명시한 비교식3개 필요')
    for name,weights in profiles.items():
        if not isinstance(name,str) or not name.strip() or not isinstance(weights,list) or len(weights)!=3:raise ValueError('이름과 시간·CCTV·조명 가중치3개 필요')
        if any(not finite(w) or w<0 for w in weights) or abs(sum(weights)-1)>1e-9:raise ValueError('가중치는 음수가 아니고 합계1이어야 함')
    selected=sorted(routes,key=lambda r:(r['minutes'],r['id']))[:3]
    fastest=selected[0]['minutes'];rankings={}
    for name,(wt,wc,wl) in profiles.items():
        scores=[{'id':r['id'],'score':wt*fastest/r['minutes']+wc*r['cctv_fraction']+wl*r['light_fraction']} for r in selected]
        scores.sort(key=lambda r:(-r['score'],r['id']))
        best=scores[0]['score']
        rankings[name]={'scores':scores,'tied_winner_ids':[r['id'] for r in scores if abs(r['score']-best)<1e-9]}
    return {'scope':'입력 후보 중 시간순3개 비교. 전체 도로망의 최단3개를 생성한 결과가 아님',
            'selected_ids':[r['id'] for r in selected],'rankings':rankings,
            'distinct_winner_count':len({rid for rank in rankings.values() for rid in rank['tied_winner_ids']}),
            'operational_policy_changed':False,'meaning':'연구용 선호 점수. 안전 확률 아님'}
