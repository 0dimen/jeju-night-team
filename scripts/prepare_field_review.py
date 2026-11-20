"""오프라인 경로 확인표 준비. 개인 집·위치 파일은 공유 저장소에 올리지 마세요."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.data.field_review import export_review
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--routes',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=export_review(args.routes,args.output)
    print('준비한 경로:',len(result['routes']),'확인할 선분:',result['review_segment_count'])
