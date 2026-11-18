"""경로 칸 없이 출처·한계를 설명하고 명시한 목록 검색을 로컬로 연결한다."""
from agent.common import check_schema,load_yaml,normalized


def wants_catalog(text):
    compact=normalized(text)
    lookup=any(term in compact for term in ('목록','후보','데이터찾','자료찾','데이터추천'))
    topic=any(term in compact for term in ('데이터','자료','cctv','가로등','보안등','보행','야간'))
    return lookup and topic


def answer():
    indicators=load_yaml('registry/indicators.yaml')
    explanation={'summary':'현재 경로 계산은 합성 자료로 시연합니다. 실제 원자료의 기준일과 사용 조건은 확인 전입니다.',
        'routes':[],'tradeoff':'경로를 입력하지 않아도 자료의 용도와 한계를 안내할 수 있습니다.',
        'not_checked':['실제 시설 원자료의 기준일','현재 시설 작동·점등 상태','출발 시각의 실제 보행량'],
        'limitations':[v['limitation'] for v in indicators.values()],
        'generated_by':'template','validation':{'passed':True,'issues':[]}}
    check_schema('explanation',explanation)
    return {'kind':'data_question','explanation':explanation,'synthetic':True,
            'data_sources':[{'indicator':key,'status':'unavailable','source_label':value['source'],
                             'note':'실제 원자료 연결 전; 현재 합성 시연용 출처 이름'} for key,value in indicators.items()]}


def lookup(text,enabled,search):
    result=answer()
    if not enabled:
        result['discovery']={'status':'disabled','adopted':False,'candidates':[]}
        result['explanation']['not_checked'].append('데이터 목록 후보 검색')
        return result
    if search is None:
        result['discovery']={'status':'unavailable','adopted':False,'candidates':[]}
        result['explanation']['summary']='데이터 목록 검색 자료가 준비되지 않았습니다. 지표 후보를 확인하지 못했습니다.'
        return result
    try:
        candidates=search.search(text,limit=10)
    except Exception:
        result['discovery']={'status':'unavailable','adopted':False,'candidates':[]}
        result['explanation']['summary']='데이터 목록 검색을 완료하지 못했습니다. 확인된 지표 후보는 없습니다.'
        return result
    if candidates.get('status')!='candidate_only' or candidates.get('adopted') is not False:
        raise ValueError('검색은 승인 전 후보만 반환해야 합니다.')
    result['discovery']=candidates
    result['synthetic']=False
    result['explanation']['summary']='실제 목록에서 찾은 검토 후보입니다. 경로 지표로 채택하거나 계산에 반영하지 않았습니다.'
    result['explanation']['not_checked']+=['후보 원자료의 좌표·기간·사용 권리','대회 지정 자료 활용 요건']
    return result
