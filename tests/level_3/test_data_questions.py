from agent.orchestrator import NightAgent
from agent.common import check_schema


def test_source_question_does_not_require_route_slots():
    result=NightAgent().run('CCTV 데이터 출처 알려줘')
    assert result['kind']=='data_question' and 'missing' not in result
    check_schema('explanation',result['explanation'])
    assert all(s['status']=='unavailable' for s in result['data_sources'])


def test_route_still_requires_missing_slots():
    assert NightAgent().run('CCTV 경로 알려줘')['kind']=='clarification'


class LocalSearch:
    def __init__(self):self.queries=[]
    def search(self,query,limit=10):
        self.queries.append(query)
        return {'status':'candidate_only','adopted':False,'candidates':[{'title':'SYNTHETIC 후보','approve':''}]}


class NeverCall:
    def generate(self,*args):raise AssertionError('내부 목록 검색은 외부 모델을 부르면 안 됨')


def test_catalog_switch_is_local_and_does_not_adopt():
    search=LocalSearch()
    agent=NightAgent({'discovery':True,'provider':'gemini','intent':'I3'},NeverCall(),discovery=search)
    result=agent.run('야간 보행 데이터 목록 찾아줘 010-0000-0000')
    assert result['kind']=='data_question'
    assert result['discovery']['status']=='candidate_only' and not result['discovery']['adopted']
    assert '010-0000-0000' not in search.queries[0]
    assert len(search.queries)==1
    check_schema('explanation',result['explanation'])


def test_disabled_catalog_does_not_call_search():
    search=LocalSearch()
    result=NightAgent({'discovery':False},discovery=search).run('CCTV 데이터 목록 찾아줘')
    assert result['discovery']['status']=='disabled' and not search.queries


def test_missing_catalog_is_unavailable_not_empty_success():
    result=NightAgent({'discovery':True}).run('가로등 데이터 후보 찾아줘')
    assert result['kind']=='data_question'
    assert result['discovery']['status']=='unavailable' and not result['discovery']['adopted']


def test_emergency_precedes_catalog_search():
    search=LocalSearch()
    result=NightAgent({'discovery':True},discovery=search).run('누가 따라와요 CCTV 데이터 목록 찾아줘')
    assert result['kind']=='emergency' and not search.queries
