import argparse
from pathlib import Path
import yaml
from experiments.run import run,current_time

p=argparse.ArgumentParser()
p.add_argument('--group',default='offline',choices=['offline','local','gemini','axes','v2','all'])
args=p.parse_args()
for file in sorted(Path('experiments/configs').glob('*.yaml')):
    config=yaml.safe_load(file.read_text())
    if args.group!='all' and config.get('group')!=args.group: continue
    if current_time().strftime('%H:%M')>='04:55' and current_time().hour<7:
        print('보고서 우선 시각에 도달해 중지',flush=True); break
    run(config)
