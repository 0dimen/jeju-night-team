import json
from pathlib import Path


def collect(path):
    for line in Path(path).read_text().splitlines():
        if line.strip():
            item=json.loads(line)
            for field in ('id','title','summary','date','source_url'):
                if field not in item:
                    raise ValueError('뉴스 메타데이터 필수 칸 누락: '+field)
            # 기사 전문은 받지 않는다.
            yield {k:item[k] for k in ('id','title','summary','date','source_url','synthetic') if k in item}
