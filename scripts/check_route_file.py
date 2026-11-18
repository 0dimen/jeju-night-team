"""준비한 경로 파일을 검사한다. 실제 길찾기나 CCTV 계산은 하지 않는다."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent.data.routes import load_routes

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);args=p.parse_args()
    data=load_routes(args.path)
    for route in data['routes']:route.pop('coordinates')
    print(json.dumps(data,ensure_ascii=False,indent=2))
