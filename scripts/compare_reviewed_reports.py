#!/usr/bin/env python3
"""저장된 비교 입력을 로컬 계산한다. 네트워크·공개 API 없음."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.data.report_effects import ReportEffectPolicy, compare_report_effects


def main():
    parser = argparse.ArgumentParser(description='승인 제보 점수 후보 비교. 운영 설정을 바꾸지 않습니다.')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--radius-m', type=float, required=True)
    parser.add_argument('--weight', type=float, required=True)
    parser.add_argument('--as-of', required=True, help='시간대가 있는 기준 시각')
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 10_000_000:
            raise ValueError('입력 크기 제한')
        data = json.loads(args.input.read_text())
        result = compare_report_effects(data['result'], data['reports'],
            ReportEffectPolicy(args.radius_m, args.weight), as_of=args.as_of, graph=data['graph'])
        # 개인 위치가 있을 수 있어 새 파일만 생성하고 소유자만 읽도록 한다.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(result, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write('\n')
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(2, '입력 형식·설정·새 출력 파일 경로를 확인해 주세요.\n')
    print('후보 비교 결과를 저장했습니다. 운영 추천은 변경하지 않았습니다.')


if __name__ == '__main__':
    main()
