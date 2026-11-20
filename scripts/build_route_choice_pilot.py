from pathlib import Path
import random,json,csv
import argparse
parser=argparse.ArgumentParser(description='합성 경로 선택 문항과 빈 응답 양식 생성')
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args();out=args.output
if out.exists() and any(out.iterdir()):raise FileExistsError('기존 문항과 응답을 보존합니다. 새 폴더를 지정하세요.')
out.mkdir(parents=True,exist_ok=True)
triples=[
[(8,20,40),(10,70,45),(11,35,90)],[(10,60,20),(11,90,30),(13,65,85)],[(12,15,80),(14,70,85),(13,35,95)],
[(6,70,25),(7,90,35),(9,75,95)],[(15,20,30),(16,75,40),(18,30,90)],[(9,80,35),(10,50,85),(12,95,60)],
[(10,30,90),(12,85,35),(11,55,65)],[(14,40,40),(15,85,50),(17,50,95)],[(7,25,70),(8,65,75),(10,90,90)],
[(16,70,20),(18,90,40),(17,45,85)],[(8,15,60),(9,80,30),(10,50,95)],[(11,45,35),(12,85,55),(14,55,90)],
[(10,90,25),(11,50,85),(13,95,70)],[(12,35,90),(13,80,60),(15,95,95)],[(6,50,40),(8,90,50),(7,60,90)],
[(18,10,70),(20,80,50),(19,40,95)],[(9,65,25),(10,90,40),(11,55,95)],[(13,30,75),(14,75,65),(16,95,90)],
[(8,80,80),(10,60,60),(12,40,40)],[(12,90,90),(13,80,80),(15,60,60)],[(6,60,70),(7,50,60),(8,40,50)],[(15,95,95),(17,75,75),(19,55,55)],
[(10,50,50),(10,50,50),(10,50,50)],[(8,75,80),(9,76,81),(10,77,82)],[(12,50,85),(12,85,50),(13,70,70)],[(10,60,60),(10,80,40),(10,40,80)]
]
triples += [triples[0],triples[5],[(10,None,70),(12,None,90),(11,None,80)],[(8,50,None),(9,70,None),(10,90,None)]]
items=[]
for i,values in enumerate(triples,1):
 kind='tradeoff' if i<=18 else 'dominance_check' if i<=22 else 'tie_or_near' if i<=26 else 'repeat' if i<=28 else 'missing_data'
 perm=list(range(3));random.Random(800+i).shuffle(perm)
 routes=[{'label':chr(65+j),'minutes':values[k][0],'cctv_percent':values[k][1],'light_percent':values[k][2]} for j,k in enumerate(perm)]
 items.append({'id':f'Q{i:02d}','synthetic':True,'design_type':kind,'repeat_of':f'Q{1 if i==27 else 6:02d}' if i in (27,28) else None,'routes':routes})
(out/'questions_SYNTHETIC.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
text=['# 경로 선택 예비 시험30문항','', '실제 길이 아닌 합성 상황입니다. 밤에 걸어서 이동하며 표에 없는 조건은 같다고 가정합니다. 같은 출발·도착의 세 경로 중 본인이 이용할 길을 고릅니다. 정답은 없습니다. 시설 인접 비율은 길이 중 시설 주변에 해당하는 비율이며 작동·밝기·안전 확률이 아닙니다. 모든 문항은 같은 방식으로 계산한 비율이라고 가정합니다. 개인 주소와 이름은 적지 않습니다.','', '선택: A/B/C, D=차이 없음, E=자료 부족·판단 보류. 이유는 시간/CCTV/조명/우회 부담/자료 부족/기타 중 고르거나 짧게 적습니다.','']
for item in items:
 text += [f'## {item["id"]}. 어느 경로를 이용하겠습니까?','', '| 경로 | 예상 시간 | CCTV 인접 비율 | 조명 인접 비율 |','|---|---:|---:|---:|']
 for row in item['routes']:
  c='자료 없음' if row['cctv_percent'] is None else str(row['cctv_percent'])+'%';l='자료 없음' if row['light_percent'] is None else str(row['light_percent'])+'%'
  text.append(f'| {row["label"]} | {row["minutes"]}분 | {c} | {l} |')
 text+=['','선택: ____ / 가장 큰 이유: ____ / 선택 확신(1~5, 선택 사항): ____','']
(out/'QUESTIONS.md').write_text('\n'.join(text))
with (out/'responses_BLANK.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['respondent','question','choice','reason','confidence'],lineterminator='\n');w.writeheader()
 for person in range(1,5):
  for q in items:w.writerow({'respondent':f'R{person:02d}','question':q['id']})
with (out/'presentation_order.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['respondent','presentation_index','question'],lineterminator='\n');w.writeheader()
 for person in range(1,5):
  ids=[q['id'] for q in items];random.Random(202600+person).shuffle(ids)
  for index,qid in enumerate(ids,1):w.writerow({'respondent':f'R{person:02d}','presentation_index':index,'question':qid})
print('합성 문항',len(items),'빈 응답',len(items)*4)
