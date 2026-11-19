"""제주시 가로등 원본에서 위도·경도가 뒤바뀐 행만 바로잡은 사본을 data/open/derived/에 만든다.

원본은 수정하지 않는다. 뒤바뀐 형태(위도 칸 126~127, 경도 칸 33~34.1)인 행만 두 값을 교환하고
'좌표수정' 열에 '위도경도교환'으로 표시한다. 그 외 행은 그대로 둔다.
agent.data.facility_cleanup은 여전히 자동 교환을 하지 않는다. 이 스크립트는 사람이 결정해 따로 실행하는 단계다.
실행: 저장소 루트에서  .venv/bin/python scripts/fix_light_axes.py
"""
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'open' / 'jeju_city_streetlights_20241010.csv'
OUT_DIR = ROOT / 'data' / 'open' / 'derived'
OUT = OUT_DIR / 'jeju_city_streetlights_20241010_axisfixed.csv'
URL = 'https://www.data.go.kr/data/15129786/fileData.do'
sys.path.insert(0, str(ROOT))
from agent.data.facility_cleanup import prepare_facilities  # noqa: E402


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = SRC.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fields = reader.fieldnames + ['좌표수정']
    swapped = Counter()
    rows = []
    for row in reader:
        lat, lon = float(row['위도']), float(row['경도'])
        row['좌표수정'] = ''
        if 126 <= lat <= 127 and 33 <= lon <= 34.1:
            row['위도'], row['경도'] = row['경도'], row['위도']
            row['좌표수정'] = '위도경도교환'
            swapped[row['법정동']] += 1
        rows.append(row)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    OUT.write_bytes(buffer.getvalue().encode('utf-8-sig'))
    before = prepare_facilities(SRC, source_name='제주특별자치도 제주시_가로등현황_20241010', source_url=URL, kind='light')
    after = prepare_facilities(OUT, source_name='제주특별자치도 제주시_가로등현황_20241010 (축 교환 복구 사본)',
                               source_url=URL, kind='light')
    note = {'source_file': SRC.name, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'output_file': OUT.name,
            'rows': len(rows), 'swapped_rows': sum(swapped.values()), 'swapped_by_dong': dict(swapped),
            'rule': '위도 칸이 126~127이고 경도 칸이 33~34.1인 행만 두 값을 교환',
            'cleanup_before': before['summary'], 'cleanup_after': after['summary'],
            'caveat': '열 뒤바뀜만 복구. 개별 좌표의 정확도·현재 설치 여부·점등 상태는 미확인'}
    (OUT_DIR / 'jeju_city_streetlights_20241010_axisfixed.note.json').write_text(
        json.dumps(note, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(note, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
