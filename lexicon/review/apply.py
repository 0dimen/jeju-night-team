"""사람이 승인 표시한 후보만 enum 예시에 추가한다. 빈 칸은 보류한다."""
import argparse
import csv
from pathlib import Path
import yaml


def apply(review,registry,output=None):
    registry=Path(registry)
    data=yaml.safe_load(registry.read_text())
    added=[]
    with open(review,newline='') as f:
        for row in csv.DictReader(f):
            if row.get('approve','').strip().lower() not in ('yes','y','true','1','승인'):
                continue
            label=row['enum']; term=row['term'].strip()
            if label not in data['preferences'] or not term or len(term)>40:
                raise ValueError('승인 후보의 enum·표현을 확인하세요.')
            if term not in data['preferences'][label]:
                data['preferences'][label].append(term)
                added.append({'enum':label,'term':term})
    target=Path(output) if output else registry
    if added:
        target.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))
    return added


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--review',default='review/lexicon_candidates.csv')
    p.add_argument('--registry',default='registry/enums.yaml')
    p.add_argument('--output')
    args=p.parse_args()
    print(apply(args.review,args.registry,args.output))
