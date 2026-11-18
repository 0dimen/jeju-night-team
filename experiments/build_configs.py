from pathlib import Path
import json
import yaml

OUT=Path(__file__).resolve().parent/'configs'
OUT.mkdir(parents=True,exist_ok=True)


def write(name,**kw):
    data={'name':name,'structure':'S1','intent':'I3','explain':'E2','provider':'mock',
          'data_scope':'synthetic','repeats':3,'group':'offline','cutoff':'04:55',**kw}
    if data['intent']=='I4':
        candidate_path=OUT.parents[1]/'review/lexicon_candidates.input.json'
        data['expanded_examples']=json.loads(candidate_path.read_text()) if candidate_path.exists() else {}
        data['lexicon_scope']='SYNTHETIC 후보만 실험; 운영 사전 승인 아님'
    (OUT/(name+'.yaml')).write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))


write('00_L0_S1_I1_E1',provider='none',intent='I1',explain='E1')
for s in ('S1','S2','S3'):
    for i in ('I1','I2','I3','I4'):
        for e in ('E1','E2','E3'):
            write(f'01_mock_{s}_{i}_{e}',structure=s,intent=i,explain=e)
selection={'intent':[0,2,4,8,18,20,23,39], 'report':[0,3,9,16,18,19,28,31],
           'explain':[0,1,4], 'flow':[0,1,5,6]}
for index,model in enumerate(('qwen3:0.6b','gemma3:1b','exaone3.5:2.4b','llama3.2:1b')):
    write('10_local_'+str(index)+'_'+model.replace(':','_'),provider='ollama',model=model,
          group='local',repeats=1,select=selection,repeat_cases={'intent':2,'report':1},timeout=75,max_wall_seconds=1500)
for s,i,e in [('S2','I3','E2'),('S3','I3','E2'),('S1','I1','E2'),('S1','I2','E2'),('S1','I4','E2'),('S1','I3','E1'),('S1','I3','E3')]:
    write(f'11_qwen_axes_{s}_{i}_{e}',structure=s,intent=i,explain=e,provider='ollama',model='qwen3:0.6b',
          group='local',repeats=1,select=selection,repeat_cases={'intent':1},timeout=75,max_wall_seconds=1200)
gemini_selection={'intent':[0,2,4,8,18,39], 'report':[0,16,18,28], 'explain':[0,1], 'flow':[0,5]}
for index,model in enumerate(('gemini-3.5-flash-lite','gemini-3.5-flash')):
    write(f'20_gemini_{index}_{model}',provider='gemini',model=model,group='gemini',repeats=1,
          select=gemini_selection,repeat_cases={'intent':2},timeout=90,max_wall_seconds=1800)
