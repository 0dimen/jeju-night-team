"""명시한 경로·시설 파일로 비교한다. 기본 시연 설정은 바꾸지 않는다."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent.data.file_engine import FileRouteEngine
from agent.orchestrator import NightAgent

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--routes',type=Path,required=True);p.add_argument('--cctv',type=Path,required=True);p.add_argument('--request',type=Path,required=True);a=p.parse_args()
    engine=FileRouteEngine(a.routes,a.cctv);agent=NightAgent(engine=engine)
    try:print(json.dumps(agent.route(json.loads(a.request.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
    finally:agent.store.db.close()
