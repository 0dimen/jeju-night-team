import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def experiment_summaries(base=None):
    base=Path(base or ROOT/'experiments/results').resolve()
    results=[];incomplete=0
    for latest in sorted(base.glob('*/latest.json')):
        try:
            pointer=json.loads(latest.read_text())
            path=(ROOT/pointer['summary']).resolve()
            if not path.is_relative_to(base):
                raise ValueError('결과 폴더 밖의 경로')
            canonical=path.with_name('analysis_v2.json')
            summary=json.loads((canonical if canonical.exists() else path).read_text())
            if not isinstance(summary,dict):
                raise ValueError('결과 형식 오류')
        except (OSError,ValueError,KeyError,TypeError):
            # 실행 중의 부분 쓰기·중단 파일은 전체 표를 실패시키지 않는다.
            incomplete+=1
            continue
        results.append({key:summary.get(key) for key in ('name','status','tasks','rule_violations','fallbacks',
                       'provider_failures','uncached_model_mean_seconds','input_tokens','output_tokens','thinking_tokens',
                       'source_phase','release_candidate','release_note','observations','unique_cases',
                       'output_and_thinking_tokens','paid_estimate_usd','cost_status','metrics_revision',
                       'report_fallbacks_recovered','report_fallback_observations_recovered')})
    return {'data':'SYNTHETIC','oracle':'AI 작성 답안 후보; 실제 사용자 정답이나 승인 아님',
            'hardware':'Raspberry Pi 5 CPU; 센터 PC 실측 아님','results':results,
            'incomplete_results':incomplete}
