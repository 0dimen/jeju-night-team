import argparse
import json
from pathlib import Path
import yaml
from discovery.catalog import CatalogSearch,ROOT
from discovery.results import experiment_summaries

p=argparse.ArgumentParser()
p.add_argument('--query')
p.add_argument('--results',action='store_true')
p.add_argument('--level',choices=['L0','L1','L2','L3'],default='L3')
p.add_argument('--limit',type=int,default=10)
args=p.parse_args()
config=yaml.safe_load((ROOT/'config/levels.yaml').read_text())['levels'][args.level]
if not config.get('discovery'):
    p.error('이 단계에서는 데이터 탐색을 켜지 않았습니다.')
if args.results:
    output=experiment_summaries()
else:
    from agent.intent.embedding import SentenceEncoder
    output=CatalogSearch(SentenceEncoder()).search(args.query or '야간 보행 경로 시설 위치',args.limit)
print(json.dumps(output,ensure_ascii=False,indent=2))
