"""실패 대체·캐시·모의를 실제 모델 세 번 생성으로 세지 않는 비교 계약."""
from scripts.summarize_experiments import repetition_metrics,used_fallback


def row(output='same',cache=False,error=False,fallback=False,provider='gemini'):
    return {'output_hash':output,'fallback':fallback,
            'provider_records':[{'provider':provider,'cache_hit':cache,'error':'QuotaReached' if error else None}]}


def test_quota_fallback_is_pipeline_repeat_but_not_three_model_responses():
    values=[row(),row(),row('fallback',error=True,fallback=True)]
    result=repetition_metrics([values])
    assert result['repeated_cases']==1 and result['reproducibility']==0
    assert result['fresh_model_repeated_cases']==0 and result['fresh_model_reproducibility'] is None


def test_cached_or_mock_repeats_are_not_new_model_generations():
    result=repetition_metrics([[row(cache=True)]*3,[row(provider='mock')]*3])
    assert result['repeated_cases']==2 and result['reproducibility']==1
    assert result['fresh_model_repeated_cases']==0


def test_three_fresh_successful_responses_can_be_compared():
    result=repetition_metrics([[row(),row(),row()]])
    assert result['fresh_model_repeated_cases']==1 and result['fresh_model_reproducibility']==1


def test_report_failure_returned_as_baseline_is_counted_without_relabeling_retry():
    failed=row(error=True)
    assert used_fallback({**failed,'task':'report'})
    assert not used_fallback({**failed,'task':'report','error':'unhandled'})
    # 설명 생성의 오류 뒤 재시도 성공은 최종 문장 틀 대체를 뜻하지 않는다.
    assert not used_fallback({**failed,'task':'explain'})
    assert not used_fallback({**row(),'task':'report'})
