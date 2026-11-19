"""원본 CSV 없이 서버 전용 계산 자료를 읽는 배포 연결."""
from functools import lru_cache
import json,os
from pathlib import Path
from threading import RLock
from agent.data.research_router import ResearchRouter,REGIONS


def get_compiled_router(region,source='standard'):
    if region not in REGIONS or source not in ('standard','datahub'):raise ValueError('지원 구간·원본 확인')
    path=Path(os.environ['JEJU_COMPILED_DATA_DIR'])/f'{region}_{source}.json'
    stat=path.stat()
    return _load(str(path),stat.st_mtime_ns,stat.st_size)


@lru_cache(maxsize=2)
def _load(path,mtime,size):
    if size>20_000_000:raise ValueError('계산 자료 크기 초과')
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if d.get('schema_version')!=1:raise ValueError('계산 자료 버전 확인')
    # 배포 생성기가 원본 검사 후 만든 서버 자료. 사용자 입력으로 생성하지 않는다.
    router=ResearchRouter.__new__(ResearchRouter)
    for k in ('region','source','label','start','goal','a','b','start_gap','end_gap','lights','cctv','sources','graph'):
        setattr(router,k,d[k])
    router.graph['nodes']={int(k):v for k,v in router.graph['nodes'].items()}
    router.graph['adjacency']={int(k):v for k,v in router.graph['adjacency'].items()}
    router.lock=RLock();router.radii=None
    return router
