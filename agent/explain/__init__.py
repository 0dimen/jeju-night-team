from copy import deepcopy
from agent.common import check_schema,load_yaml,normalized,INDICATOR_NAMES
from agent.validate import validate_explanation
from agent.explain.connectors import CONNECTORS


def template_explanation(analysis, mode='route_compare'):
    check_schema('analysis_result', analysis)
    import json
    content=json.dumps(analysis,ensure_ascii=False)
    if any(normalized(p) in normalized(content) for p in load_yaml('registry/forbidden_phrases.yaml')['phrases']):
        raise ValueError('엔진의 설명에 허용되지 않은 단정 문구가 있습니다.')
    if any(term in normalized(content) for term in ('현재보행자수는','실시간보행량','지금사람이')):
        raise ValueError('월별 자료를 현재 보행량으로 표현할 수 없습니다.')
    texts = []
    for route in analysis['routes']:
        parts = [f"{route['id']}: {route['distance']}, {route['duration']}"]
        for name, indicator in route['indicators'].items():
            label=INDICATOR_NAMES.get(name,name)
            if indicator['status'] == 'unavailable':
                parts.append(f'{label}: 데이터 없음; 계산에서 제외')
            elif indicator['status'] == 'pending':
                parts.append(f'{label}: 검토 중; 경로 지표에 반영하지 않음')
            elif indicator['status']=='historical':
                parts.append(('과거 통계: ' if name=='activity' else '과거 기준일 자료: ')+indicator.get('display',name))
            else:
                parts.append(indicator.get('display', name))
        texts.append({'id': route['id'], 'text': '. '.join(parts)})
    summary = {'route_compare': '시설 인접 구간과 이동 거리·시간을 비교합니다.',
               'reanalysis': '검증 후 게시된 시설 상태로 다시 계산한 결과입니다.',
               'data_question': '출처와 확인하지 못한 항목을 함께 보여 드립니다.'}[mode]
    result = {'summary': summary, 'routes': texts, 'tradeoff': analysis['comparison']['detour'],
              'not_checked': sorted(set(analysis['unavailable_preferences']) | {
                  k for r in analysis['routes'] for k,v in r['indicators'].items() if v['status'] == 'unavailable'}),
              'limitations': list(analysis['limitations']), 'generated_by': 'template',
              'validation': {'passed': True, 'issues': []}}
    result['not_checked']=[INDICATOR_NAMES.get(name,name) for name in result['not_checked']]
    return check_schema('explanation', result)


def explain(analysis, provider=None, mode='route_compare', method='E1'):
    template = template_explanation(analysis, mode)
    if provider is None or method == 'E1':
        return template
    issues = []
    for attempt in range(2):
        try:
            if method=='E3':
                connection=provider.generate('connect',{'summary':template['summary'],
                    'limitations':template['limitations'],'candidates':CONNECTORS,'previous_issues':issues})
                if connection.get('connector') not in CONNECTORS:
                    raise ValueError('허용하지 않는 연결 문장')
                candidate=deepcopy(template)
                candidate['summary']+=' '+connection['connector']
            else:
                candidate = provider.generate('explain', {'analysis': analysis, 'template': template,
                                              'method': method, 'previous_issues': issues})
            issues = validate_explanation(candidate, analysis, template)
            if not issues:
                candidate = deepcopy(candidate)
                candidate['generated_by'] = 'hybrid' if method == 'E3' else 'llm'
                candidate['validation'] = {'passed': True, 'issues': []}
                return candidate
        except Exception as exc:
            # 키나 원문이 오류에 섞이지 않도록 오류 종류만 기록한다.
            issues = ['provider_error:' + type(exc).__name__]
    template['validation']['issues'] = ['fallback_after_two_attempts'] + issues
    return template
