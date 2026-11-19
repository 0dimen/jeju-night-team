from agent.report import classify,resolve_with_choice
from agent.common import check_schema


def classify_with_model(text,user_choice=None,provider=None):
    baseline=classify(text,user_choice)
    if provider is None or baseline['emergency']:
        return baseline
    try:
        output=provider.generate('report',{'text':baseline['summary'],'user_choice':user_choice or {},
                                           'precheck':baseline})
        check_schema('report_classification',output)
        # 모델은 시설·문제만 제안한다. 개인정보·긴급·원문 요약은 코드 결과 유지.
        for key in ('facility','problem','confidence'):
            baseline[key]=output[key]
        baseline['facility'],baseline['problem'],baseline['conflict_with_user_choice']=resolve_with_choice(baseline,user_choice)
    except Exception:
        pass
    return baseline
