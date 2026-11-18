"""숫자는 경로별로 검사한다. 핵심 필드는 코드가 만든 문장과 일치해야 한다."""
import json
import re
from agent.common import check_schema, normalized, load_yaml


def numbers(text):
    return re.findall(r'\d+(?:\.\d+)?', text)


def validate_explanation(candidate, analysis, template):
    issues = []
    try:
        check_schema('explanation', candidate)
    except Exception:
        return ['schema_invalid']
    content = json.dumps({k: v for k, v in candidate.items() if k != 'validation'}, ensure_ascii=False)
    if any(normalized(p) in normalized(content) for p in load_yaml('registry/forbidden_phrases.yaml')['phrases']):
        issues.append('R4_forbidden_phrase')
    if any(word in normalized(content) for word in ['현재보행자', '야간보행자수는', '실시간보행량', '지금사람이']):
        issues.append('R6_monthly_as_realtime')
    # 자유 서술을 신뢰하지 않고 허용된 핵심 문장을 보존한다.
    for field in ['summary', 'tradeoff', 'not_checked', 'limitations']:
        if field=='summary':
            from agent.explain.connectors import CONNECTORS
            if candidate[field] in [template[field]]+[template[field]+' '+c for c in CONNECTORS]:
                continue
        if candidate[field] != template[field]:
            issues.append('protected_' + field)
    expected = {r['id']: r['text'] for r in template['routes']}
    actual = {r['id']: r['text'] for r in candidate['routes']}
    if len(actual) != len(candidate['routes']) or set(actual) != set(expected):
        issues.append('route_set_mismatch')
    for rid, text in actual.items():
        if rid not in expected:
            continue
        if numbers(text) != numbers(expected[rid]):
            issues.append('R1_route_number_mismatch:' + rid)
        if text != expected[rid]:
            issues.append('protected_route_evidence:' + rid)
    if numbers(content) != numbers(json.dumps({k:v for k,v in template.items() if k != 'validation'}, ensure_ascii=False)):
        # 경로별 대조가 주 검사다. 전체 대조는 추가된 숫자만 찾는다.
        from collections import Counter
        allowed = Counter(numbers(json.dumps(template, ensure_ascii=False)))
        extra = Counter(numbers(content)) - allowed
        if extra:
            issues.append('R1_unsupported_numbers')
    return sorted(set(issues))
