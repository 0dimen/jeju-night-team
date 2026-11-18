from experiments.run import plan_for,manifest_for,hashable_output
from experiments.metrics import summarize
from experiments.run import load_cases


def test_datasets_minimums_and_ambiguity():
    for task,minimum in [('intent',40),('report',30),('explain',15),('flow',10)]:
        rows=load_cases(task)
        assert len(rows)>=minimum
        assert len({r['id'] for r in rows})==len(rows)
        assert all(r['synthetic'] and r['expected'] for r in rows)
    assert any(r['ambiguous'] for r in load_cases('intent'))


def test_repeats_are_actual_separate_planned_calls():
    config={'limits':{'intent':2,'report':0,'explain':0,'flow':0},'repeats':1,'repeat_cases':{'intent':1}}
    planned=plan_for(config)
    assert len(planned)==4
    assert [r for t,c,r in planned if c['id']=='SYNTHETIC-INTENT-000']==[0,1,2]


def test_manifest_changes_when_config_changes():
    a=manifest_for({'name':'SYNTHETIC','intent':'I1'})
    b=manifest_for({'name':'SYNTHETIC','intent':'I3'})
    assert a['signature']!=b['signature']


def test_quantitative_reproducibility_preserves_route_ids():
    assert hashable_output({'id':'A'})!={'id':'B'}
    assert hashable_output({'id':'SYNTHETIC-RPT-foo','text':'x'})=={'text':'x'}


def test_deadline_fair_schedule_preserves_cases_and_repetitions():
    from collections import Counter
    config={'limits':{'intent':5,'report':2,'explain':1,'flow':3},
            'repeats':1,'repeat_cases':{'intent':2}}
    sequential=plan_for(config)
    balanced=plan_for({**config,'schedule':'round_robin'})
    keys=lambda plan:Counter((task,case['id'],repeat) for task,case,repeat in plan)
    assert keys(sequential)==keys(balanced)
    assert {task for task,_,_ in balanced[:4]}=={'intent','report','explain','flow'}
    assert all(repeat==0 for _,_,repeat in balanced[:11])
    assert balanced==plan_for({**config,'schedule':'round_robin'})
