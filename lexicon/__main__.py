import argparse
import json
from pathlib import Path
from lexicon.sources.local_files import collect
from lexicon.methods.cooccurrence import compute
from lexicon.store import save
from lexicon.review import export
from lexicon.adapters.input_side import candidates
from lexicon.adapters.output_side import candidates as output_candidates

p=argparse.ArgumentParser()
p.add_argument('--input',default='data/news_input/SYNTHETIC_news.jsonl')
p.add_argument('--out',default='review/lexicon_candidates.csv')
p.add_argument('--store',default='lexicon/store/terms.parquet')
args=p.parse_args()
Path(args.out).parent.mkdir(parents=True,exist_ok=True)
rows=compute(list(collect(args.input)))
save(rows,args.store); export(rows,args.out)
Path(args.out).with_suffix('.input.json').write_text(json.dumps(candidates(rows),ensure_ascii=False,indent=2)+'\n')
export(output_candidates(rows),Path(args.out).with_name('lexicon_output_candidates.csv'),
       fieldnames=['term','kind','evidence','approve'])
print(json.dumps({'rows':len(rows),'source':args.input,'approved':False},ensure_ascii=False))
