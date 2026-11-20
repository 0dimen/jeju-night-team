"""CSV 원본의 행수와 파일10줄·데이터10행을 구분해 출력한다. 원본 수정 없음."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path


def inspect(path,encoding):
    raw=Path(path).read_bytes();text=raw.decode(encoding)
    physical=text.splitlines()
    with Path(path).open(encoding=encoding,newline='') as stream:
        reader=csv.DictReader(stream);rows=list(reader)
    if not rows:raise ValueError('데이터 행이 없는 CSV입니다.')
    result={'file':Path(path).name,'sha256':hashlib.sha256(raw).hexdigest(),'encoding':encoding,
            'headers':reader.fieldnames,'data_rows_excluding_header':len(rows),'physical_line_count_including_header':len(physical),
            'physical_line_10_including_header':physical[9] if len(physical)>=10 else None,
            'data_record_10_excluding_header':rows[9] if len(rows)>=10 else None}
    if '설치목적' in reader.fieldnames:
        result['purpose_counts']=dict(Counter(row['설치목적'] for row in rows))
        result['declared_camera_counts_by_purpose']={}
        for purpose in result['purpose_counts']:
            selected=[row for row in rows if row['설치목적']==purpose]
            counts=[int(row['카메라대수']) for row in selected]
            result['declared_camera_counts_by_purpose'][purpose]=sum(counts)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('--encoding',required=True)
    args=parser.parse_args()
    print(json.dumps(inspect(args.source,args.encoding),ensure_ascii=False,indent=2))
