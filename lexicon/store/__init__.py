from pathlib import Path
import json
import hashlib
import pyarrow as pa
import pyarrow.parquet as pq


def save(rows,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows),path)
    version=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path.with_suffix('.version.json').write_text(json.dumps({'sha256':version,'rows':len(rows),'approved':False},ensure_ascii=False,indent=2)+'\n')
