"""실행 전에 고정하는 AI 작성 답안 후보. 실제 출력에서 정답을 역산하지 않는다."""
import json
from pathlib import Path
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/datasets'


def write(name,rows):
    OUT.mkdir(parents=True,exist_ok=True)
    for index,row in enumerate(rows):
        row.update(id=f'SYNTHETIC-{name.upper()}-{index:03}',synthetic=True,
                   oracle_source='docs/INSTRUCTIONS.md v2 + AI 작성 답안 후보; 사람 승인 전',
                   split='calibration' if index%3==0 else 'evaluation')
        row.setdefault('ambiguous',False)
    (OUT/f'{name}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))


def main():
    # 문구마다 기대 선호를 먼저 명시한다. 표현이 같은 복제 사례로 개수를 늘리지 않는다.
    phrases=[
      ('제주시청에서 탑동광장까지 CCTV 있는 길로', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 가로등 많은 경로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 어둡지 않은 데로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 인적 있는 길로', 'route',['activity']),
      ('제주시청에서 탑동광장까지 카메라와 가로등', 'route',['cctv','streetlight']),
      ('제주공항에서 동문시장까지 사람 다니는 길로', 'route',['activity']),
      ('동문시장에서 탑동광장까지 선호 없음', 'route',['none']),
      ('제주시청에서 탑동광장까지 컴컴하지 않은 길로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 환한 쪽으로 가려 해', 'route',['streetlight']),
      ('제주공항에서 동문시장까지 씨씨티비 많은 곳으로', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 조명이 있는 길로', 'route',['streetlight']),
      ('동문시장에서 탑동광장까지 상관없어', 'route',['none']),
      ('제주시청에서 탑동광장까지 북적이는 경로', 'route',['activity']),
      ('탑동광장에서 제주시청까지 불빛 있는 길로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 가로등이랑 CCTV랑', 'route',['cctv','streetlight']),
      ('제주공항에서 동문시장까지 어두운 골목을 피하는 경로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 아무거나', 'route',['none']),
      ('동문시장에서 탑동광장까지 거리에 사람이 있으면 좋겠어', 'route',['activity']),
      ('제주시청에서 탑동광장까지 가로등은 상관없고 CCTV 우선', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 CCTV 말고 조명', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 보안등 있는 데로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 카메라와 사람 다니는 경로', 'route',['cctv','activity']),
      ('제주시청에서 탑동광장까지 밝은 길로 갑서', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 씨씨티브이 쪽으로', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 가로동 있는 길로', 'route',['streetlight']),
      ('탑동광장으로 가려는데 출발지는 아직 못 정했어', 'route',['none']),
      ('제주시청에서 출발하는 경로 알려줘', 'route',['none']),
      ('CCTV를 참고하는 밤길을 비교해 줘', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 조용한 데로', 'route',['none']),
      ('제주시청에서 탑동광장까지 가로등과 인적을 참고하는 경로', 'route',['streetlight','activity']),
      ('가로등이 깜빡이는 시설을 제보할게', 'report',['streetlight']),
      ('CCTV 고장 제보', 'report',['cctv']),
      ('보행로 파손 제보', 'report',['none']),
      ('불 꺼짐 제보', 'report',['none']),
      ('가로등 데이터의 기준일은 언제야', 'data_question',['streetlight']),
      ('방문객 통계는 실시간이야', 'data_question',['activity']),
      ('CCTV 출처 알려줘', 'data_question',['cctv']),
      ('월별 통계를 밤 보행량으로 쓸 수 있어', 'data_question',['none']),
      ('오늘 저녁 맛집 추천해 줘', 'unsupported',['none']),
      ('내일 비가 올까', 'unsupported',['none']),
      ('택시 예약해 줘', 'unsupported',['none']),
      ('안녕', 'unsupported',['none']),
      ('제주시청에서 탑동광장까지 전부 보장해 주는 경로', 'route',['none']),
      ('제주시청에서 탑동광장까지 010-0000-0000으로 경로 알려줘', 'route',['none']),
      ('제주시청에서 탑동광장까지 어두운 것보다 밝은 골목으로', 'route',['streetlight']),
      ('제주시청에서 탑동광장까지 폐쇄회로 장비 옆으로', 'route',['cctv']),
      ('제주시청에서 탑동광장까지 사람 없는 곳으로', 'route',['none']),
      ('제주시청에서 탑동광장까지 CCTV 없이도 괜찮아', 'route',['none']),
      ('CCTV가 어두워요', 'report',['cctv']),
      ('길이 불편해요', 'report',['none']),
      ('밝고 조용한 길로', 'route',['streetlight']),
      ('지금 한적한가요', 'data_question',['activity']),
    ]
    # 위치는 입력 순서에서 추출할 수 있는 명시 값만 답안에 둔다.
    places=['제주시청','탑동광장','제주공항','동문시장']
    rows=[]
    ambiguous={28,48,49,50,51}
    for i,(text,kind,pref) in enumerate(phrases):
        departure='2026-11-18T22:00' if i%4!=0 and kind=='route' else None
        if departure: text+=' '+departure
        ordered=sorted((text.index(name),name) for name in places if name in text)
        # 단일 위치가 '으로'에 붙은 경우 목적지이며 출발지는 미정.
        origin=ordered[0][1] if ordered and not (len(ordered)==1 and '출발지' in text) else None
        dest=ordered[1][1] if len(ordered)>1 else (ordered[0][1] if len(ordered)==1 and '출발지' in text else None)
        rows.append({'text':text,'expected':{'kind':kind,'preferences':pref,'origin_name':origin,
                     'destination_name':dest,'departure':departure},'ambiguous':i in ambiguous})
    write('intent',rows)
    cases=[
      ('가로등 불 꺼짐','streetlight','not_working'),('CCTV가 고장났어요','cctv','not_working'),
      ('보행로가 막혀요','walkway','obstructed'),('가로등이 깜빡여요','streetlight','flickering'),
      ('보안등이 부서졌어요','streetlight','damaged'),('불이 꺼져 있어요','streetlight','not_working'),
      ('카메라가 깨졌어요','cctv','damaged'),('인도에 물건이 적치되어 있어요','walkway','obstructed'),
      ('가로등이 안 켜져요','streetlight','not_working'),('골목이 너무 컴컴해요','other','too_dark'),
      ('CCTV가 가려져 있어요','cctv','obstructed'),('가로등 불빛이 약해요','streetlight','too_dark'),
      ('길바닥이 파손됐어요','walkway','damaged'),('보안등 깜박거림','streetlight','flickering'),
      ('불 꺼짐','streetlight','not_working'),('보행로 통행 막힘','walkway','obstructed'),
      ('가로등 꺼짐 010-0000-0000','streetlight','not_working'),
      ('CCTV 고장 user@example.invalid','cctv','not_working'),
      ('누가 따라와요','other','other'),('골목에서 폭행 중이에요','other','other'),
      ('가로등이 깜빡이고 주변이 어두워요','streetlight','flickering'),
      ('가로등이 고장나서 어두워요','streetlight','not_working'),
      ('보행로가 깨지고 막혔어요','walkway','damaged'),
      ('카메라 작동 안 해요','cctv','not_working'),('가로등이 반짝여요','streetlight','flickering'),
      ('보안등이 깨짐','streetlight','damaged'),('가로등이 컴컴해요','streetlight','too_dark'),
      ('가로등이 가려졌어요','streetlight','obstructed'),('신호등 고장','other','not_working'),
      ('인도에 나뭇가지가 막혔어요','walkway','obstructed'),('설명을 잘 모르겠어요','other','other'),
      ('CCTV와 가로등이 모두 안 켜져요','other','not_working'),
      ('불이 이상해요','other','other'),('CCTV가 어둡게 보여요','cctv','too_dark'),
      ('가로등 꺼짐 900101-1000000','streetlight','not_working'),
      ('살려 주세요 누가 따라오고 있어요','other','other'),
    ]
    rows=[]
    for i,(text,facility,problem) in enumerate(cases):
        choice={'facility':'cctv','problem':'not_working'} if i in (0,3,8) else {}
        rows.append({'text':text,'user_choice':choice,
          'expected':{'facility':facility,'problem':problem,'emergency':i in (18,19,35),
                      'personal_info_masked':i in (16,17,34),
                      'conflict_with_user_choice':bool(choice and (choice['facility']!=facility or choice['problem']!=problem))},
          'ambiguous':i in (20,21,22,31,32,33)})
    write('report',rows)
    variants=[('normal','route_compare'),('missing_all','route_compare'),('tie','route_compare'),
              ('single','route_compare'),('reanalysis','reanalysis'),('data_question','data_question'),
              ('pending','route_compare'),('empty_routes','route_compare'),('no_sources','data_question'),
              ('cctv_missing','route_compare'),('all_historical','data_question'),('zero_verified','route_compare'),
              ('long_limitations','route_compare'),('preference_unavailable','route_compare'),
              ('reanalysis_single','reanalysis'),('large_radius','route_compare')]
    write('explain',[{'variant':variant,'mode':mode,'expected':{'schema_valid':True,'R1':True,'R3':True,'R4':True,'R6':True}} for variant,mode in variants])
    flows=[
      ('route_complete','제주시청에서 탑동광장까지 CCTV 2026-11-18T22:00','route'),
      ('route_missing_time','제주시청에서 탑동광장까지 밝은 길로','clarification'),
      ('route_missing_origin','탑동광장까지 가려 해','clarification'),
      ('report_location','가로등 꺼짐 제보','report'),
      ('report_missing_location','가로등 깜빡임 제보','clarification'),
      ('emergency','누가 따라와요','emergency'),
      ('pii','가로등 꺼짐 제보 010-0000-0000','report'),
      ('unsupported','택시 예약해 줘','unsupported'),
      ('data','CCTV 데이터 기준일','data_question'),
      ('review_publish_reanalysis','CCTV 고장 제보','report'),
      ('conflicting_choice','가로등 꺼짐 제보','report'),
      ('historical','방문객 통계는 현재 보행자 수야','data_question')]
    request=json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text())
    rows=[]
    for scenario,text,kind in flows:
        context={}
        if scenario in ('report_location','pii','review_publish_reanalysis','conflicting_choice'):
            context={'lat':33.5,'lng':126.5}
        if scenario=='conflicting_choice': context['user_choice']={'facility':'cctv'}
        if kind=='data_question': context={'request':request}
        rows.append({'scenario':scenario,'text':text,'context':context,'expected':{'kind':kind}})
    write('flow',rows)


if __name__=='__main__':
    main()
