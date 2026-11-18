import re
from agent.common import load_yaml, normalized
from agent.report import mask_personal_info

PLACES = {'제주시청': (33.4996, 126.5312), '탑동광장': (33.517, 126.525),
          '제주공항': (33.5104, 126.4913), '동문시장': (33.5117, 126.526)}


def parse(text):
    text, _ = mask_personal_info(text)
    if any(w in text for w in ['제보', '고장', '깜빡', '꺼짐', '파손', '불 꺼', '불이 꺼']):
        kind = 'report'
    elif any(w in text for w in ['데이터', '통계', '출처', '기준일', '방문객']):
        kind = 'data_question'
    elif any(w in text for w in ['에서', '까지', '경로', '가려', '가는', '길로', '밤길', '데로']):
        kind = 'route'
    else:
        kind = 'unsupported'
    compact=normalized(text)
    def wanted(term):
        term=normalized(term)
        if term not in compact:return False
        pattern=re.escape(term)+r'(?:은|는|이|가|도|을|를)?(?:말고|제외|상관없|필요없|없이|없어도|없는)'
        return re.search(pattern,compact) is None
    pref = [k for k, terms in load_yaml('registry/enums.yaml')['preferences'].items()
            if any(wanted(t) for t in terms)]
    if len(pref) > 1 and 'none' in pref:
        pref.remove('none')
    places = sorted(((text.index(name), name) for name in PLACES if name in text))
    request = {'preferences': pref or ['none']}
    explicit={'origin':[],'destination':[]}
    for _,name in places:
        for occurrence in re.finditer(re.escape(name),text):
            tail=text[occurrence.end():]
            if re.match(r'\s*(?:에서|으로부터|로부터)',tail):
                explicit['origin'].append(name)
            elif re.match(r'\s*(?:까지|으로|로|에(?!서))',tail):
                explicit['destination'].append(name)
    explicit={field:list(dict.fromkeys(names)) for field,names in explicit.items()}
    assigned={field:names[0] for field,names in explicit.items() if len(names)==1}
    if not any(explicit.values()):
        assigned=dict(zip(('origin','destination'),[name for _,name in places])) if len(places)<=2 else {}
    elif len(places)==2:
        for field,other in [('origin','destination'),('destination','origin')]:
            if not explicit[field] and other in assigned:
                remaining=[name for _,name in places if name!=assigned[other]]
                if len(remaining)==1:assigned[field]=remaining[0]
    # 서로 다른 출발/도착 후보가 여러 개면 임의로 첫 장소를 고르지 않는다.
    for field,name in assigned.items():
        lat, lng = PLACES[name]
        request[field] = {'name': name, 'lat': lat, 'lng': lng}
    date = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', text)
    if date:
        request['departure'] = date.group()
    uncertain = [f for f in ('origin', 'destination', 'departure') if f not in request] if kind == 'route' else []
    return {'kind': kind, 'request': request, 'uncertain_fields': uncertain, 'method': 'keyword'}
