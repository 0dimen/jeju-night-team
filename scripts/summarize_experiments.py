"""원시 사례는 보존하고, 반복에 가중되지 않는 사례별 비교표를 따로 만든다."""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
import json
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def percent(value): return '미측정' if value is None else f'{value*100:.1f}%'
def number(value): return '미측정' if value is None else f'{value:.2f}'


def used_fallback(row):
    # 제보 분류는 공급자 오류를 잡아 규칙 결과를 반환한다. 초기 runner는
    # 이 경로의 fallback 표시를 빠뜨렸으므로 원시 공급자 기록으로 보완한다.
    return bool(row.get('fallback') or (row.get('task')=='report' and not row.get('error')
        and any(call.get('error') for call in row.get('provider_records',[]))))


def repetition_metrics(groups):
    completed=[g for g in groups if len(g)>=3 and not any(r.get('error') for r in g)]
    fresh=[g for g in completed if all(r.get('provider_records') and not used_fallback(r)
            and all(not c.get('error') and not c.get('cache_hit')
                    and c.get('provider') in ('gemini','ollama','openai','anthropic')
                    for c in r['provider_records']) for r in g)]
    def rate(values):
        return mean(len({r['output_hash'] for r in g})==1 for g in values) if values else None
    return {'repeated_cases':len(completed),'reproducibility':rate(completed),
            'fresh_model_repeated_cases':len(fresh),'fresh_model_reproducibility':rate(fresh)}


def load_runs():
    runs=[]
    base=ROOT/'experiments/results'
    for pointer in sorted(base.glob('*/latest.json')):
        info=json.loads(pointer.read_text());path=ROOT/info['summary']
        summary=json.loads(path.read_text())
        phases=json.loads((ROOT/'experiments/results/model_setup/runtime_phases.json').read_text()) if (ROOT/'experiments/results/model_setup/runtime_phases.json').exists() else {}
        source_phase=summary['config'].get('phase')
        if not source_phase:
            prompt_hash=summary['manifest'].get('file_sha256',{}).get('agent/llm/schemas.py')
            source_phase='initial_v1' if prompt_hash==phases.get('initial_v1',{}).get('prompt_sha256') else 'version_from_manifest'
        rows=[json.loads(line) for line in path.with_name('cases.jsonl').read_text().splitlines()]
        first={}
        groups=defaultdict(list)
        for row in rows:
            key=(row['task'],row['case_id'])
            groups[key].append(row)
            if key not in first or row['repeat']<first[key]['repeat']: first[key]=row
        metrics={}
        for task in ('intent','report','explain','flow'):
            selected=[r for (t,_),r in first.items() if t==task]
            valid=[r for r in selected if not r['ambiguous'] and r.get('correct') is not None]
            evaluation=[r for r in valid if r['split']=='evaluation']
            repeated=[v for (t,_),v in groups.items() if t==task and len(v)>=3 and not any(r.get('error') for r in v)]
            metrics[task]={'unique_cases':len(selected),'scored_cases':len(valid),'ambiguous_cases':len(selected)-len(valid),
                'accuracy':mean(r['correct'] for r in valid) if valid else None,
                'evaluation_cases':len(evaluation),'evaluation_accuracy':mean(r['correct'] for r in evaluation) if evaluation else None,
                'slot_accuracy':mean(r.get('slot_accuracy',0.) for r in valid) if valid else None,
                'mean_seconds':mean(r['elapsed_seconds'] for r in selected) if selected else None,
                'max_seconds':max((r['elapsed_seconds'] for r in selected),default=None),
                'repeated_cases':len(repeated),'reproducibility':mean(len({r['output_hash'] for r in group})==1 for group in repeated) if repeated else None}
            model_success=[r for r in valid if r.get('provider_records') and not used_fallback(r)
                           and all(not c.get('error') and c.get('provider') in ('gemini','ollama','openai','anthropic')
                                   for c in r['provider_records'])]
            metrics[task]['model_success_cases']=len(model_success)
            metrics[task]['model_success_accuracy']=mean(r['correct'] for r in model_success) if model_success else None
            metrics[task]['provider_error_cases']=sum(any(c.get('error') for c in r.get('provider_records',[])) for r in selected)
            metrics[task].update(repetition_metrics([v for (t,_),v in groups.items() if t==task]))
        calls=[c for r in rows for c in r.get('provider_records',[]) if not c.get('cache_hit')]
        tokens_in=sum(c.get('input_tokens') or 0 for c in calls)
        tokens_out=sum((c.get('output_tokens') or 0)+(c.get('thinking_tokens') or 0) for c in calls)
        rates={'gemini-3.5-flash-lite':(.30,2.50),'gemini-3.6-flash':(.75,3.75)}
        priced=[]
        for call in calls:
            actual=call.get('actual_model',call.get('model',''))
            if actual in rates and call.get('input_tokens') is not None:
                inp,out=rates[actual]
                priced.append(((call.get('input_tokens') or 0)*inp+
                    ((call.get('output_tokens') or 0)+(call.get('thinking_tokens') or 0))*out)/1e6)
        paid=sum(priced) if priced else None
        canonical={'name':summary['name'],'status':summary['status'],'config':summary['config'],
                   'source_phase':source_phase,'release_candidate':source_phase=='post_report_v7',
                   'release_note':('현재 검토 경계 보강 코드. 기술 검사 후보이며 사람 승인·실데이터·센터 PC 검증은 별도'
                       if source_phase=='post_report_v7' else '이전 코드 판은 후속 검토 경계 검사 실패로 제출 코드 후보에서 제외. 정상 사례의 모델 비교 참고용'),
                   'metrics_revision':4,'aggregation':'각 사례의 첫 관측만 정확도에 사용. 애매 사례 제외. 전체 처리와 새 모델 응답의 반복 재현성 별도. 제보 공급자 오류 뒤 규칙 대체는 원시 기록으로 복원',
                   'tasks':metrics,'unique_cases':len(first),'observations':len(rows),
                   'rule_violations':sum(bool(r.get('rule_issues')) for r in rows),
                   'failures':sum(bool(r.get('error')) for r in rows),
                   'provider_failures':sum(bool(c.get('error')) for r in rows for c in r.get('provider_records',[])),
                   'explain_fallback_rate':mean(r.get('fallback',False) for (t,_),r in first.items() if t=='explain') if any(t=='explain' for t,_ in first) else None,
                   'fallbacks':sum(used_fallback(r) for r in first.values()),
                   'report_fallbacks_recovered':sum(used_fallback(r) and not r.get('fallback') for r in first.values()),
                   'report_fallback_observations_recovered':sum(used_fallback(r) and not r.get('fallback') for r in rows),
                   'uncached_calls':len(calls),'cached_calls':sum(c.get('cache_hit',False) for r in rows for c in r.get('provider_records',[])),
                   'uncached_model_mean_seconds':mean(c['elapsed_seconds'] for c in calls) if calls else None,
                   'input_tokens':tokens_in,'output_and_thinking_tokens':tokens_out,
                   'paid_estimate_usd':paid,'cost_status':'무료 등급으로 측정, 유료 전환 시 추정 비용' if summary['config']['provider']=='gemini' else '로컬·mock: API 비용 없음; 전력 비용 미측정',
                   'price_source':'https://ai.google.dev/gemini-api/docs/pricing', 'price_checked_at':'2026-11-18',
                   'price_note':'응답이 보고한 실제 모델로 계산. 3.6 Flash의 현재 단가는 2026-12-31까지 적용. 오류 호출 토큰은 제공되지 않아 전체 비용은 모름',
                   'peak_work_rss_bytes':summary['manifest'].get('peak_work_rss_bytes'),
                   'rss_measurement_scope':'현재 실행 프로세스 공간의 Python RSS. 공유 Ollama 서버는 보이지 않아 model_setup/local_resource_summary.json의 적재 크기와 따로 봐야 함',
                   'seed_note':('초기 로컬 반복은 42/43/44 시드. 고정 시드 재현성으로 해석하지 않음' if source_phase=='initial_v1' else '로컬 시드 42 고정; 반복 번호는 캐시 분리용') if summary['config']['provider']=='ollama' else '동일 입력, 온도 0; 반복 번호는 캐시 분리용',
                   'original_summary':str(path.relative_to(ROOT))}
        path.with_name('analysis_v2.json').write_text(json.dumps(canonical,ensure_ascii=False,indent=2)+'\n')
        runs.append({'summary':summary,'canonical':canonical,'first':first,'rows':rows,'path':path})
    return runs


def common_comparison(runs, hardened=False, full=False):
    prefixes=('40_v3','41_v3','42_current') if full else (('30_v2','31_v2','32_v2','36_v2') if hardened else ('00_L0','10_local_','20_gemini_'))
    chosen=[r for r in runs if r['summary']['name'].startswith(prefixes)
            and (r['canonical']['source_phase']!='initial_v1' if hardened or full else r['canonical']['source_phase']=='initial_v1')]
    if not chosen:return []
    # 미완료 모델이 없는 사례 때문에 공통 집합이 부당하게 줄지 않도록 완료 조합만 비교.
    chosen=[r for r in chosen if r['summary']['status']=='completed']
    keys=set.intersection(*(set(r['first']) for r in chosen)) if chosen else set()
    rows=[]
    for run in chosen:
        c=run['canonical']
        for task in ('intent','report','explain','flow'):
            selected=[run['first'][key] for key in sorted(keys) if key[0]==task and not run['first'][key]['ambiguous']]
            rows.append({'configuration':c['name'],'source_phase':c['source_phase'],'model':c['config'].get('model','none'), 'task':task,
                         'matched_cases':len(selected),'accuracy':mean(r['correct'] for r in selected) if selected else None,
                         'mean_seconds':mean(r['elapsed_seconds'] for r in selected) if selected else None,
                         'rule_violations':sum(bool(r.get('rule_issues')) for r in selected),'approve':''})
    path=ROOT/('review/p6_full_matched_cases_SYNTHETIC.csv' if full else ('review/p6_model_matched_cases_v2_SYNTHETIC.csv' if hardened else 'review/p6_model_matched_cases_SYNTHETIC.csv'))
    if rows:
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n"); writer.writeheader();writer.writerows(rows)
    return rows


def disagreement(runs):
    grouped=defaultdict(list)
    for run in runs:
        if not run['summary']['name'].startswith(('00_L0','10_local_','20_gemini_','30_v2','31_v2','32_v2','36_v2','40_v3','41_v3','42_current','45_priority','50_post','51_post','52_post')):continue
        for key,row in run['first'].items():
            if key[0] not in ('intent','report') or 'output' not in row:continue
            value=row['output']
            if key[0]=='intent': candidate={'kind':value['kind'],'preferences':value['request']['preferences']}
            else: candidate={k:value.get(k) for k in ('facility','problem')}
            grouped[key].append((run['summary']['name'],candidate))
    rows=[]
    for (task,cid),outputs in grouped.items():
        if len({json.dumps(v,sort_keys=True) for _,v in outputs})>1:
            rows.append({'task':task,'case_id':cid,'method_outputs':json.dumps(dict(outputs),ensure_ascii=False),
                         'decision':'모델 간 차이로 정답을 확정하지 않음. 합성 입력과 후보 답안을 사람이 확인','approve':''})
    path=ROOT/'review/p7_model_disagreement_SYNTHETIC.csv'
    if rows:
        with path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)


def post_comparison(runs):
    """부분 실행도 작업별 공통 사례로 비교하고, 정상 응답 없는 한도 실패는 분리한다."""
    selected=[r for r in runs if r['summary']['name'].startswith(('40_v3','41_v3','45_priority','50_post','51_post','52_post'))]
    output=[]
    for task in ('intent','report','explain','flow'):
        participants=[]
        for run in selected:
            keys={key for key,row in run['first'].items() if key[0]==task and not row['ambiguous'] and row.get('correct') is not None}
            if keys:participants.append((run,keys))
        keys=set.intersection(*(keys for _,keys in participants)) if participants else set()
        for run,_ in participants:
            rows=[run['first'][key] for key in sorted(keys)];c=run['canonical']
            output.append({'configuration':c['name'],'model':c['config'].get('model','none'),
                'source_phase':c['source_phase'],'run_status':c['status'],'task':task,
                'participating_configurations':len(participants),'matched_cases':len(rows),
                'accuracy':mean(r['correct'] for r in rows) if rows else None,
                'mean_seconds':mean(r['elapsed_seconds'] for r in rows) if rows else None,
                'fallback_cases':sum(used_fallback(r) for r in rows),
                'provider_error_cases':sum(any(c.get('error') for c in r.get('provider_records',[])) for r in rows),
                'rule_violations':sum(bool(r.get('rule_issues')) for r in rows),'approve':''})
    if output:
        with (ROOT/'review/p6_post_matched_cases_SYNTHETIC.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(output[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(output)
    return output


def error_audit(runs):
    datasets={task:{case['id']:case for case in map(json.loads,
        (ROOT/'experiments/datasets'/f'{task}.jsonl').read_text().splitlines())}
        for task in ('intent','report')}
    rows=[]
    for run in runs:
        c=run['canonical']
        if not c['name'].startswith(('40_v3','41_v3','45_priority','50_post','51_post','52_post')):continue
        for (task,cid),record in run['first'].items():
            if task not in datasets or record['ambiguous'] or record.get('correct') is not False:continue
            case=datasets[task][cid]
            if not case.get('synthetic'):raise ValueError('합성 오류 사례만 내보냅니다.')
            rows.append({'configuration':c['name'],'source_phase':c['source_phase'],'run_status':c['status'],
                'task':task,'case_id':cid,'split':case['split'],'text':case['text'],
                'expected_candidate':json.dumps(case['expected'],ensure_ascii=False),
                'actual_output':json.dumps(record.get('output'),ensure_ascii=False),
                'mismatched_fields':','.join(record.get('mismatched_fields',[])),
                'provider_error':any(call.get('error') for call in record.get('provider_records',[])),
                'fallback':used_fallback(record),'oracle':'AI 작성 답안 후보; 사람 검토 전',
                'next_step':'후보 답안의 뜻부터 검토한 뒤 새 표현·별도 시험 세트 준비. 현재 사전 미변경','approve':''})
    if rows:
        with (ROOT/'review/p6_error_cases_SYNTHETIC.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    return rows


def paired_errors(runs):
    baseline=next((r for r in runs if r['canonical']['name'].startswith('45_priority')),None)
    if baseline is None:return []
    rows=[]
    for run in runs:
        c=run['canonical']
        if not c['name'].startswith(('40_v3','41_v3','50_post','51_post','52_post')):continue
        for task in ('intent','report'):
            pairs=[(baseline['first'][key],run['first'][key])
                   for key in sorted(baseline['first'].keys()&run['first'].keys())
                   if key[0]==task and not baseline['first'][key]['ambiguous']
                   and not run['first'][key]['ambiguous']
                   and baseline['first'][key].get('correct') is not None
                   and run['first'][key].get('correct') is not None]
            if not pairs:continue
            row={'configuration':c['name'],'source_phase':c['source_phase'],'run_status':c['status'],
                 'task':task,'matched_cases':len(pairs),
                 'both_correct':sum(a['correct'] and b['correct'] for a,b in pairs),
                 'baseline_only_correct':sum(a['correct'] and not b['correct'] for a,b in pairs),
                 'model_pipeline_only_correct':sum(not a['correct'] and b['correct'] for a,b in pairs),
                 'both_wrong':sum(not a['correct'] and not b['correct'] for a,b in pairs),
                 'model_pipeline_fallbacks':sum(used_fallback(b) for _,b in pairs),
                 'note':'AI 후보 답안·관측한 공통 사례. 코드판 차이 있음. 결합 모델의 정확도로 해석하지 않음','approve':''}
            assert sum(row[k] for k in ('both_correct','baseline_only_correct','model_pipeline_only_correct','both_wrong'))==len(pairs)
            rows.append(row)
    if rows:
        with (ROOT/'review/p6_paired_errors_SYNTHETIC.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    return rows


def report(runs):
    now=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M KST')
    lines=['# 실험 비교', '', '결론: 아래 표는 실제 저장된 실행 결과를 집계한다. 합성 입력·AI 작성 답안 후보의 결과이며 실제 사용자 정확도가 아니다.', '',
      f'집계 시각: {now}. 코드·입력 해시와 원시 사례는 각 조합 폴더에 보존했다. `analysis_v2.json`은 반복 횟수로 정확도가 가중되지 않도록 각 사례의 첫 관측만 사용한 재집계다. 이름이 30 이상인 조합은 경계·프롬프트를 보강한 판이다. 현재 제출 코드 후보는 검토 후 분류 보호와 직접 호출의 긴급 우선까지 보강한 post_report_v7이다. 이전 코드 판은 후속 검토 경계 검사 실패 때문에 정상 사례 비교 참고로만 남겼다.', '',
      '## 먼저 볼 비교', '', '| 구성·모델 | 최종 입력 정확도(사례 수) | 모델 성공 입력 정확도(성공 수) | 최종 제보 정확도(사례 수) | 설명 대체 비율 | 최종 규칙 위반 | 공급자 오류 | 실제 호출 평균(초) | 상태 |', '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for run in runs:
        c=run['canonical']
        if c['config'].get('group')=='offline' and c['config']['provider']=='mock':continue
        a=c['tasks']['intent'];b=c['tasks']['report']
        model_result='미사용' if c['config']['intent'] in ('I1','I2') else f"{percent(a['model_success_accuracy'])} ({a['model_success_cases']})"
        lines.append(f"| {c['name']} | {percent(a['accuracy'])} ({a['scored_cases']}) | {model_result} | {percent(b['accuracy'])} ({b['scored_cases']}) | {percent(c['explain_fallback_rate'])} | {c['rule_violations']} | {c['provider_failures']} | {number(c['uncached_model_mean_seconds'])} | {c['status']} |")
    lines+=['', '## 무료 API 측정과 유료 전환 추정', '',
      '실제 유료 호출은 하지 않았다. 아래는 무료 등급으로 측정한 정상 응답의 입력·출력·추론 토큰에 공개 단가를 적용한 값이다. 캐시 적중은 새 호출 비용으로 세지 않는다. 오류 호출 토큰은 알 수 없어 전체 비용은 모름이다. 로컬·mock·모델 없는 구성은 API 비용이 없고 전력 비용은 미측정이다.', '',
      '| 구성 | 입력 토큰 | 출력·추론 토큰 | 유료 전환 추정(달러, 정상 응답 하한) | 공급자 오류 횟수 |',
      '|---|---:|---:|---:|---:|']
    for run in runs:
        c=run['canonical']
        if c['config']['provider']!='gemini':continue
        paid='모름' if c['paid_estimate_usd'] is None else f"{c['paid_estimate_usd']:.7f}"
        lines.append(f"| {c['name']} | {c['input_tokens']} | {c['output_and_thinking_tokens']} | {paid} | {c['provider_failures']} |")
    lines+=['', '## 입력 반복 결과', '',
      '전체 처리의 반복은 오류 대체까지 포함한다. 모델 반복은 세 관측 모두 실제 모델 응답에 성공하고 캐시·mock·대체를 사용하지 않은 그룹만 센다. 무료 한도나 오류로 기본 방식으로 바뀐 결과를 실제 모델의 세 번 생성으로 세지 않는다. 아래 수치는 전체 출력 지문 기준이며 의미 정답률과 별개다.', '',
      '| 구성 | 전체 처리 같은 출력(반복 사례 수) | 실제 모델 같은 출력(새 응답 반복 사례 수) |',
      '|---|---:|---:|']
    for run in runs:
        c=run['canonical'];m=c['tasks']['intent']
        if c['config']['provider']=='mock':continue
        lines.append(f"| {c['name']} | {percent(m['reproducibility'])} ({m['repeated_cases']}) | {percent(m['fresh_model_reproducibility'])} ({m['fresh_model_repeated_cases']}) |")
    lines+=['', '## 같은 사례만 비교', '', '표본 수가 다른 전체 표의 순위를 그대로 비교하지 않는다. 초기 판은 `review/p6_model_matched_cases_SYNTHETIC.csv`, 보강판은 `review/p6_model_matched_cases_v2_SYNTHETIC.csv`에서 각 버전 안의 공통 사례만 비교한다. 보강판 네 구성은 입력 4·제보 3·설명 1·흐름 2건을 공유한다. 반복·애매 사례는 정확도 분모에서 제외한다.', '',
      '보고 후 비교는 `review/p6_post_matched_cases_SYNTHETIC.csv`에 작업별로 정리한다. 해당 작업을 실제 실행한 구성만 참여하고 부분 실행의 공통 사례 수를 함께 쓴다. 정상 모델 응답0건인 중급 무료 한도 실패는 성능 비교에서 분리한다. 코드의 검토·개인정보 처리 보강 시점이 달라 전체 흐름을 순수 모델 단독 효과로 해석하지 않는다.', '',
      '집계4판: 제보 분류에서 공급자 오류 뒤 규칙 결과를 반환한 경로는 원시 공급자 기록으로 대체 여부를 복원한다. 원시 fallback 필드는 변경하지 않는다. 설명의 재시도 성공을 최종 문장 틀 대체로 바꾸지 않는다. mock 응답은 실제 모델 성공 건수에서 제외한다.', '',
      '틀린 입력·제보는 `review/p6_error_cases_SYNTHETIC.csv`에서 문장·후보 정답·출력·틀린 칸·버전을 함께 본다. 현재 기본안은 입력5건의 선호 표현과 제보1건의 밝기 문제를 놓쳤다. 후보 정답을 먼저 검토하고 새 별도 시험 문장을 준비해야 하며 기존 사전을 자동 수정하지 않았다.', '',
      '규칙과 모델이 서로 고친 사례는 `review/p6_paired_errors_SYNTHETIC.csv`에 있다. Gemini 경량의 공통 입력47건 중 둘 다 일치36·규칙만 일치6·모델 처리만 일치5·둘 다 불일치0이다. 모델이 규칙 실패를 모두 고쳤어도 다른6건을 새로 놓쳤다. 어느 답을 고를지 결정하는 기능을 별도 검증하지 않았으므로 두 답의 합집합을 결합 정확도로 주장하지 않는다.', '',
      '기호: S1=고정 흐름, S2=도구 계획형, S3=요청 종류만 모델 판단. I1=키워드 규칙, I2=문장 벡터, I3=모델과 허용 값, I4=모델과 연관어 예시. E1=문장 틀, E2=모델 우선, E3=틀과 연결 문장.', '',
      '## 확대 비교', '',
      '05시 보고 전57개 완료 설정은 원본 합성116사례를 여러 설정·반복으로 관측한 결과다. 확대 비교의 같은 비애매 입력47건에서 현재 규칙89.4%·Qwen 0.8b25.5%·Gemini 경량87.2%, 제보30건은96.7%·86.7%·100%, 흐름12건은100%·75%·100%였다. 최종 규칙 위반은 모두0이었다. 모델 성공 사례와 규칙 대체 후 결과는 따로 본다. 공통 사례와 분모는 `review/p6_full_matched_cases_SYNTHETIC.csv`에 있다. 두 모델은 같은 시작 코드의 비교지만 현재 규칙은 이후 경로 방향·선택 값 검사를 보강한 판이므로 세 구성 전체를 엄밀한 모델 단독 효과로 해석하지 않는다. 원본은116사례이며 관측 수를 새 독립 표본으로 세지 않는다.', '',
      '## 축별 해석', '',
      '- 구조: Qwen 0.6b의 같은 흐름 4건에서 고정형·도구 계획형은 각각 75%, 종류 판단형은 100%였다. 평균 전체 시간은 각각 8.62·13.59·15.83초다. 표본이 작고 모델 해석 오류가 섞여 종류 판단형을 운영 우승으로 확정하지 않는다. 모델 없는 고정형은 전체 흐름 12건 100%이고 호출 지연이 없어 기본안으로 추천한다. 도구 계획은 읽기만 허용하며 승인·게시 권한은 없다.',
      '- 입력: 같은 입력 8건에서 규칙 75%, 문장 벡터 37.5%, Qwen 0.6b 모델 12.5%, 연관어 확장 모델 12.5%, Qwen 0.8b 모델 37.5%였다. 규칙의 보강판 전체 47건은 89.4%다. 규칙을 기본으로 추천하고 생략·방언·복수 문제의 확인 요청을 추가 보강해야 한다. 합성 연관어를 넣어도 이번 표본에서는 개선이 없었으므로 자동 사전 반영을 하지 않는다. Gemini 경량은 별도 공통 입력 4건 100%로, 이 8건과 분모가 다르다.',
      '- 설명: 같은 설명 3건에서 문장 틀·모델 우선·틀과 연결 문장은 모두 최종 규칙 검사 100%, 대체 0%였다. 전체 평균은 문장 틀 0.010초, 모델 우선 87.46초, Qwen 0.6b 연결 문장 4.52초다. 문장 틀이 가장 빠르므로 기본으로 추천한다. 모델 우선은 근거 문장을 그대로 유지하는 보수적 구현으로 자유 설명 품질 비교가 아니다. 연결 문장은 허용된 세 문장 중 하나만 선택한다.',
      '- 모델: API와 로컬은 실제 호출을 했으며, Anthropic·OpenAI는 키 없음으로 미실행했다. 표의 정확도는 규칙 대체를 포함한 최종 파이프라인 결과다. 모델 호출이 성공한 사례만의 정확도와 공급자 오류 사례 수는 analysis_v2.json의 model_success_accuracy·provider_error_cases로 따로 보존한다. 작은 표본·합성 문장·공유 CPU에서 얻은 속도이며 제출 센터의 GPU 실측으로 확대하지 않는다.', '',
      '현재 코드의 모의 공급자 구조 3종은 각각 348회 관측을 완료했다. 고정 흐름·도구 계획형·요청 종류 판단형 모두 입력 89.4%·제보 96.7%·흐름 100%·최종 규칙 위반 0건이었다. 모의 공급자의 설정 전환·보호 흐름 검사이며 실제 모델의 계획 성능·정확도 비교가 아니다.', '',
      '중단 상태는 원시 실행기의 표기를 보존한다. 후속 Llama의 paused_for_report는 05시 보고 완료 후 설정한 06:45 호출 종료를 뜻한다. Gemma의 paused_budget는 20분 예산, 중급 Gemini의 quota_exhausted는 무료 한도 도달이다. 부분 결과를 완료 설정이나 새 모델 3회 생성으로 세지 않는다.', '',
      '## 반복·속도·비용의 한계', '',
      '전체 처리 반복에는 오류 뒤 기본 대체도 포함한다. 실제 모델 반복은 세 관측 모두 새 모델 생성에 성공한 그룹만 집계한다. 기본 보강판의 제보 검토 후 재분석 흐름 1건은 반복마다 새 게시 이벤트 식별자·시각으로 데이터 버전이 달라 전체 출력이 달랐다. 이 경우를 같은 데이터 버전의 정량 비결정성으로 해석하지 않는다. 원시 전체 출력 재현성 수치는 보존한다. 초기 로컬은 시드 42·43·44를 사용했으므로 고정 시드 재현성으로 주장하지 않는다. 보강판은 시드 42를 고정했다. Gemini는 최대 10건 이하 일부 사례만 반복했다. 요청 전체 시간에는 캐시·재생성·대체가 포함되며, 표의 모델 호출 평균은 캐시 적중을 제외한 실제 호출 시간이다. 초기 오프라인 검사·로컬 추론·무료 API 실험이 같은 기기에서 겹친 구간이 있어 순수 모델 간 속도 순위로 해석하지 않는다.', '',
      '무료 등급으로 측정, 유료 전환 시 추정 비용은 실제 제공된 입력·출력·추론 토큰에 단가를 곱했다. 오류 호출의 토큰은 알 수 없어 제외한 하한값이며 전체 비용은 모름이다. 2026-11-18 [Google 공식 가격](https://ai.google.dev/gemini-api/docs/pricing)에서 3.5 Flash-Lite와 응답이 보고한 실제 중급 모델 3.6 Flash의 단가를 확인했다. 요청 이름 3.5 Flash를 실제 모델 이름으로 간주하지 않는다.', '',
      '## 오프라인 설정 조합', '', '| 구성 | 입력 정확도 | 제보 정확도 | 설명 규칙 검사 | 흐름 정확도 | 규칙 위반 |', '|---|---:|---:|---:|---:|---:|']
    for run in runs:
        c=run['canonical']
        if c['config']['provider']!='mock':continue
        t=c['tasks']
        lines.append(f"| {c['name']} | {percent(t['intent']['accuracy'])} | {percent(t['report']['accuracy'])} | {percent(t['explain']['accuracy'])} | {percent(t['flow']['accuracy'])} | {c['rule_violations']} |")
    lines+=['', '판정: 최종 규칙 위반이 하나라도 있는 조합은 채택 대상에서 제외한다. 모델 초안이 거부되어 기본 문장으로 대체된 경우는 초안 실패와 최종 규칙 준수를 따로 기록한다. 숫자·반경·임계값·모델 선택은 사람 승인 전 추천이다.', '']
    (ROOT/'EXPERIMENTS.md').write_text('\n'.join(lines))
    aggregate=[r['canonical'] for r in runs]
    (ROOT/'experiments/results/summary_v2.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    runs=load_runs();common_comparison(runs);common_comparison(runs,hardened=True);common_comparison(runs,full=True);post_comparison(runs);disagreement(runs);error_audit(runs);paired_errors(runs);report(runs)
    print('조합 집계',len(runs))
