"""설정 하나를 실행한다. 사례별 저장·코드/입력 해시·실제 반복 호출을 구분한다."""
import argparse
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
import threading

import psutil
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent.common import stable_hash,check_schema
from agent.intent.methods import interpret
from agent.report.model import classify_with_model
from agent.explain import explain,template_explanation
from agent.validate import validate_explanation
from agent.orchestrator import NightAgent
from agent.llm import make_provider
from experiments.cases import explanation_input
from experiments.metrics import summarize


def load_cases(task):
    return [json.loads(line) for line in (ROOT/'experiments/datasets'/f'{task}.jsonl').read_text().splitlines()]


def manifest_for(config):
    sources=sorted([*ROOT.glob('agent/**/*.py'),*ROOT.glob('stubs/**/*.py'),*ROOT.glob('lexicon/**/*.py'),
                    *ROOT.glob('experiments/*.py'),*ROOT.glob('experiments/datasets/*.jsonl'),*ROOT.glob('contracts/*.json'),
                    *ROOT.glob('registry/*.yaml')])
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    return {'signature':stable_hash([config,hashes]),'file_sha256':hashes,
            'hardware':'Raspberry Pi 5 aarch64 4 cores RAM 15.8GiB no GPU; local inference 2 threads',
            'data':'SYNTHETIC','oracle':'AI 후보 답안; 사람 승인 전','started_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}


def current_time():
    return datetime.now(ZoneInfo('Asia/Seoul'))


class ResourceMonitor:
    def __init__(self):
        self.stop=threading.Event(); self.peak_rss=0; self.exceeded=False
        self.thread=threading.Thread(target=self.watch,daemon=True)
    def watch(self):
        while not self.stop.is_set():
            own=psutil.Process()
            processes=[own,*own.children(recursive=True)]
            for p in psutil.process_iter(['name']):
                if 'ollama' in (p.info['name'] or '').lower(): processes.append(p)
            rss=0
            for p in {p.pid:p for p in processes}.values():
                try: rss+=p.memory_info().rss
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            self.peak_rss=max(self.peak_rss,rss)
            if rss>8_000_000_000: self.exceeded=True
            self.stop.wait(.5)
    def __enter__(self): self.thread.start(); return self
    def __exit__(self,*args): self.stop.set(); self.thread.join(timeout=2)


def plan_for(config):
    schedule=config.get('schedule','task_order')
    if schedule not in ('task_order','round_robin'):
        raise ValueError('알 수 없는 실험 순서입니다.')
    plan=[]
    for task in ('intent','report','explain','flow'):
        cases=load_cases(task)
        indices=config.get('select',{}).get(task)
        if indices is not None: cases=[cases[i] for i in indices]
        if task in config.get('limits',{}): cases=cases[:config['limits'][task]]
        for index,case in enumerate(cases):
            repeats=config.get('repeats',1)
            if index<config.get('repeat_cases',{}).get(task,0): repeats=max(repeats,3)
            for repeat in range(repeats): plan.append((task,case,repeat))
    if schedule=='round_robin':
        # 마감 중단에서도 네 작업을 관측한다. 사례 선택·반복 수는 바꾸지 않는다.
        # 첫 관측을 먼저 모으고, 재현성용 추가 반복은 뒤에 수행한다.
        queues={task:[row for row in plan if row[0]==task and row[2]==0]
                for task in ('intent','report','explain','flow')}
        first=[]
        for index in range(max(map(len,queues.values()),default=0)):
            first.extend(queue[index] for queue in queues.values() if index<len(queue))
        return first+[row for row in plan if row[2]>0]
    return plan


def score_fields(actual,expected):
    flags={k:actual.get(k)==v for k,v in expected.items()}
    return all(flags.values()),sum(flags.values())/len(flags),[k for k,v in flags.items() if not v]


def execute(task,case,config,provider,embedding,request):
    rule_issues=[]; fallback=False
    if task=='intent':
        output=interpret(case['text'],config['intent'],provider,embedding,
                         config.get('expanded_examples',{}))
        req=output['request']
        actual={'kind':output['kind'],'preferences':req['preferences'],
                'origin_name':req.get('origin',{}).get('name'),'destination_name':req.get('destination',{}).get('name'),
                'departure':req.get('departure')}
        actual['preferences']=sorted(actual['preferences'])
        expected={**case['expected'],'preferences':sorted(case['expected']['preferences'])}
        correct,slot,mismatch=score_fields(actual,expected)
        fallback=bool(output.get('fallback_reason'))
    elif task=='report':
        output=classify_with_model(case['text'],case.get('user_choice'),provider)
        check_schema('report_classification',output)
        correct,slot,mismatch=score_fields(output,case['expected'])
        if output['emergency']!=case['expected']['emergency']: rule_issues.append('R9')
        if output['personal_info_masked']!=case['expected']['personal_info_masked']: rule_issues.append('R10')
    elif task=='explain':
        data=explanation_input(case,request)
        output=explain(data,provider,case['mode'],config['explain'])
        template=template_explanation(data,case['mode'])
        rule_issues=validate_explanation(output,data,template)
        correct=not rule_issues; slot=float(correct); mismatch=rule_issues
        fallback=bool(config['explain']!='E1' and output['generated_by']=='template')
    else:
        agent=NightAgent(config,provider,embedding=embedding)
        try:
            output=agent.run(case['text'],case['context'])
            correct,slot,mismatch=score_fields(output,case['expected'])
            if 'analysis' in output:
                rule_issues=validate_explanation(output['explanation'],output['analysis'],
                     template_explanation(output['analysis'],'data_question' if output['kind']=='data_question' else 'route_compare'))
            if case['scenario']=='emergency' and not output.get('message','').startswith('긴급한 상황이면 먼저 112'):
                rule_issues.append('R9')
            if case['scenario']=='pii' and '010-0000-0000' in json.dumps(output,ensure_ascii=False):
                rule_issues.append('R10')
            output['trace']=agent.trace
            fallback=any(t.get('fallback') or t.get('step')=='structure_fallback' for t in agent.trace)
            if case['scenario']=='review_publish_reanalysis' and output.get('kind')=='report':
                rid=output['report']['id']
                before=agent.route(request)
                agent.store.transition(rid,'VERIFIED','synthetic-admin','합성 검증 근거')
                agent.store.publish(rid,'CCTV-B1','cctv','normal','not_working','synthetic-admin','합성 확인')
                after=agent.route(request,mode='reanalysis')
                if before['analysis']['data_version']==after['analysis']['data_version']: rule_issues.append('reanalysis_missing')
                output['reanalysis']={'before':before,'after':after}
        finally:
            agent.store.close()
    return output,correct,slot,mismatch,rule_issues,fallback


def hashable_output(output):
    # 제보 식별자·실행 시각은 재현성 대상에서 제외한다. 정량 필드는 유지한다.
    if isinstance(output,dict):
        return {k:hashable_output(v) for k,v in output.items()
                if k not in ('report_id','verified_at','trace')
                and not (k=='id' and isinstance(v,str) and v.startswith('SYNTHETIC-RPT-'))}
    if isinstance(output,list): return [hashable_output(v) for v in output]
    return output


def run(config):
    manifest=manifest_for(config)
    base=ROOT/'experiments/results'/config['name']
    out=base/manifest['signature']; out.mkdir(parents=True,exist_ok=True)
    summary_path=out/'summary.json'
    if summary_path.exists():
        saved=json.loads(summary_path.read_text())
        if saved.get('status') in ('completed','quota_exhausted'):
            print(config['name'],'skip',saved['status'],flush=True)
            return saved
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    case_path=out/'cases.jsonl'
    if case_path.exists():
        # 중단된 마지막 줄만 제외하고 완료 사례를 이어 간다.
        for line in case_path.read_text().splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: break
        case_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    done={(r['task'],r['case_id'],r['repeat']) for r in rows}
    cutoff=config.get('cutoff','04:55')
    hour,minute=map(int,cutoff.split(':'))
    deadline=current_time().replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp() if current_time().hour<7 else None
    provider=make_provider({**config,'deadline':deadline,'cache_dir':str(ROOT/'experiments/results'/config['name']/'cache')}) if config.get('provider','none')!='none' else None
    embedding=None
    if config['intent']=='I2':
        try:
            from agent.intent.embedding import SentenceEncoder,PreferenceClassifier
            embedding=PreferenceClassifier(SentenceEncoder(),config.get('threshold',.62))
        except Exception as exc:
            manifest['embedding_error']=type(exc).__name__
    request=json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text())
    start=perf_counter(); status='completed'; plan=plan_for(config)
    with ResourceMonitor() as resources:
        for task,case,repeat in plan:
            if (task,case['id'],repeat) in done: continue
            now=current_time()
            cutoff=config.get('cutoff','04:55')
            if now.strftime('%H:%M')>=cutoff and now.hour<7:
                status='paused_for_report'; break
            if perf_counter()-start>config.get('max_wall_seconds',1200):
                status='paused_budget'; break
            if resources.exceeded:
                status='memory_limit'; break
            if provider: provider.repeat=repeat
            previous=len(provider.records) if provider else 0
            tick=perf_counter()
            row={'task':task,'case_id':case['id'],'repeat':repeat,'split':case['split'],
                 'ambiguous':case['ambiguous'],'correct':None,'rule_issues':[]}
            try:
                output,correct,slot,mismatch,issues,fallback=execute(task,case,config,provider,embedding,request)
                row.update(output=output,correct=correct,slot_accuracy=slot,mismatched_fields=mismatch,
                           rule_issues=issues,fallback=fallback,output_hash=stable_hash(hashable_output(output)))
            except Exception as exc:
                row.update(error=type(exc).__name__,correct=False,slot_accuracy=0.,output_hash=stable_hash(type(exc).__name__))
            row['elapsed_seconds']=perf_counter()-tick
            row['provider_records']=provider.records[previous:] if provider else []
            with case_path.open('a') as f:
                f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush(); os.fsync(f.fileno())
            rows.append(row)
            print(config['name'],task,case['id'],repeat,'ok' if row['correct'] else 'different',round(row['elapsed_seconds'],2),flush=True)
            if provider and (provider.quota_failed or any(c.get('error')=='QuotaReached' for c in row['provider_records'])):
                status='quota_exhausted'; break
        manifest['peak_work_rss_bytes']=resources.peak_rss
    if provider: provider.close()
    result=summarize(rows,config,manifest)
    result.update(status=status,planned_observations=len(plan),finished_at=current_time().isoformat())
    summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (base/'latest.json').write_text(json.dumps({'signature':manifest['signature'],'summary':str(summary_path.relative_to(ROOT))},indent=2)+'\n')
    print(config['name'],status,len(rows),'/',len(plan),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    args=p.parse_args()
    run(yaml.safe_load(Path(args.config).read_text()))
