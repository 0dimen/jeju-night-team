"""수집한 경로로 빈 현장 확인표를 준비한다. 확인 결과를 추측하지 않는다."""
import csv
import json
from pathlib import Path
from agent.data.routes import load_routes

CHECKS = ('통행 가능 여부', '횡단 지점', '야간 밝기', '공사·폐쇄', '시설 현재 상태')

def export_review(route_path, output_dir):
    loaded = load_routes(route_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for route in loaded['routes']:
        for index, (start, end) in enumerate(zip(route['coordinates'], route['coordinates'][1:]), 1):
            rows.append({'route_id': route['id'], 'segment': index,
                'start_lng': start[0], 'start_lat': start[1], 'end_lng': end[0], 'end_lat': end[1],
                '통행 가능 여부': '', '횡단 지점': '', '야간 밝기': '', '공사·폐쇄': '', '시설 현재 상태': '',
                '확인 날짜·시각': '', '확인 방법': '', '근거': '', '메모': ''})
    fields = list(rows[0])
    with (out/'field_review.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    summary = {'source_sha256': loaded['source_sha256'], 'source': loaded['metadata'],
        'scope': '빈 현장 확인표. 현장 확인·안전 판정·서비스 채택을 수행하지 않음.',
        'onsite_verified_by_export': False,
        'routes': [{key: route[key] for key in ('id', 'length_m', 'duration_minutes', 'duration_basis')} for route in loaded['routes']],
        'review_segment_count': len(rows), 'all_review_answers_blank': True}
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary
