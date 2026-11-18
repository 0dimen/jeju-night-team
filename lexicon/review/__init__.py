import csv
import hashlib
from pathlib import Path


def export(rows,path,fieldnames=None):
    rows=list(rows)
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        with path.open(newline='') as stream:
            annotated=any(row.get('approve','').strip() for row in csv.DictReader(stream))
        if annotated:
            original=path.read_bytes();digest=hashlib.sha256(original).hexdigest()[:16]
            history=path.parent/'.history';history.mkdir(exist_ok=True)
            snapshot=history/(path.stem+'.'+digest+'.csv')
            if not snapshot.exists():snapshot.write_bytes(original)
    fields=fieldnames or (list(rows[0]) if rows else ['enum','term','score','method','source_count',
        'sentence_ids','example_1','example_2','source_urls','approve'])
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)
