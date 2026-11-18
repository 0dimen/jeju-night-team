"""저장 전 제보 후보와 확인 질문. 사람의 답이나 정답을 대신 정하지 않는다."""
from agent.common import load_yaml,normalized
from agent.report import classify,emergency_check,mask_personal_info


def preview_report(text,user_choice=None):
    if emergency_check(text):
        return {'kind':'emergency','stored':False,
                'message':load_yaml('registry/emergency_phrases.yaml')['message']}
    candidate=classify(text,user_choice)
    masked,_=mask_personal_info(text)
    enums=load_yaml('registry/enums.yaml');compact=normalized(masked)
    questions=[]
    for field,label in [('facility','시설'),('problem','문제')]:
        mentions=[key for key,terms in enums[field].items()
                  if any(normalized(term) in compact for term in terms)]
        if len(mentions)>1:
            questions.append({'field':field,'message':f'여러 {label} 표현이 있습니다. 먼저 처리할 {label} 한 가지를 확인해 주세요.',
                              'mentioned_candidates':mentions})
        elif candidate[field]=='other':
            questions.append({'field':field,'message':f'어떤 {label}인지 더 설명해 주세요.','mentioned_candidates':mentions})
    if any(term in compact for term in ('아니','말고','않','아닌')):
        questions.append({'field':'meaning','message':'부정 표현이 있습니다. 실제로 발생한 문제를 확인해 주세요.'})
    if candidate['facility']=='cctv' and candidate['problem']=='too_dark':
        questions.append({'field':'meaning','message':'카메라 영상이 어두운 것인지, 주변 길이 어두운 것인지 확인해 주세요.'})
    if '비상벨' in compact:
        questions.append({'field':'facility','message':'비상벨은 현재 별도 시설 항목이 없습니다. 처리할 시설을 검토해 주세요.'})
    if candidate['conflict_with_user_choice']:
        questions.append({'field':'user_choice','message':'선택한 항목과 자동 후보가 다릅니다. 사람이 확인해야 합니다.'})
    return {'kind':'report_preview','stored':False,'classification_candidate':candidate,
            'questions':questions,'requires_human_review':True,
            'message':'자동 분류 후보입니다. 정답·게시 승인이 아니며 아직 저장하지 않았습니다.'}
