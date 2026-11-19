import re
import unicodedata
from agent.common import load_yaml, normalized, check_schema


def mask_personal_info(text):
    if not isinstance(text,str):
        raise ValueError('텍스트를 입력해야 합니다.')
    text=unicodedata.normalize('NFKC',text)
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    text=re.sub(r'[\u2010-\u2015\u2212\ufe63\uff0d]','-',text)
    text=re.sub(r'(?<!\d)\((0\d{1,3})\)(?=[ \t.-]*\d)',r'\1',text)
    text=re.sub(r'\+82[ \t]*\(0\)[ \t]*(?=1)', '+82 ',text)
    text=re.sub(r'(?<=\d)[ \t\r\n]+(?=\d)',' ',text)
    masked = text
    for pattern in load_yaml('registry/pii_patterns.yaml')['patterns']:
        masked = re.sub(pattern, '[개인정보 가림]', masked)
    return masked, masked != text


def emergency_check(text):
    spec = load_yaml('registry/emergency_phrases.yaml')
    return any(normalized(x) in normalized(text) for x in spec['phrases'])


def safe_report_summary(text):
    # 사용자 제보의 단정 표현을 서비스의 판단처럼 다시 출력하지 않는다.
    for phrase in load_yaml('registry/forbidden_phrases.yaml')['phrases']:
        letters=[c for c in unicodedata.normalize('NFKC',phrase) if c.isalnum()]
        pattern=r'[\W_]*'.join(re.escape(c) for c in letters)
        text=re.sub(pattern,'[단정 표현 생략]',text,flags=re.IGNORECASE)
    return text


def match_enum(text, group, default='other'):
    matches = [key for key, examples in load_yaml('registry/enums.yaml')[group].items()
               if any(normalized(term) in normalized(text) for term in examples)]
    return matches[0] if matches else default


def resolve_with_choice(auto, choice):
    """자동 분류가 모르는 칸(other)은 사용자가 고른 값을 따른다. 다른 값을 분명히 고른 칸만 충돌로 본다."""
    choice = choice or {}
    final = {}
    for key in ('facility', 'problem'):
        picked = choice.get(key)
        final[key] = picked if auto[key] == 'other' and picked not in (None, 'other') else auto[key]
    conflict = any(choice.get(k) not in (None, final[k]) for k in ('facility', 'problem'))
    return final['facility'], final['problem'], conflict


def classify(text, user_choice=None):
    text, masked = mask_personal_info(text)
    facility = match_enum(text, 'facility')
    problem = match_enum(text, 'problem')
    choice = user_choice or {}
    if not isinstance(choice,dict):
        raise ValueError('사용자 선택은 허용 값의 객체여야 합니다.')
    enums=load_yaml('registry/enums.yaml')
    for field in ('facility','problem'):
        value=choice.get(field)
        if value is not None and (not isinstance(value,str) or value not in enums[field]):
            raise ValueError('허용되지 않은 시설·문제 선택입니다.')
    unsure = 'other' in (facility, problem)
    facility, problem, conflict = resolve_with_choice({'facility': facility, 'problem': problem}, choice)
    result = dict(facility=facility, problem=problem, summary=safe_report_summary(text)[:500],
                  confidence=0.5 if conflict or unsure else 0.85,
                  conflict_with_user_choice=conflict, personal_info_masked=masked,
                  emergency=emergency_check(text))
    return check_schema('report_classification', result)
