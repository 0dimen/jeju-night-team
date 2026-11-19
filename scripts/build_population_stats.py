"""제주데이터허브 748번(유동인구에 따른 카드 매출액 변화 매쉬업결과)에서 읍면동·월별 거주·근무·방문인구를 만든다.

원본 CSV 는 받은 그대로 data/open/population/ 에 두고, 화면용 집계만 data/population/ 에 쓴다.
원본의 인구 값은 '월 × 읍면동 × 성별' 단위로 업종마다 반복되므로 성별별 한 값을 더한다.
값은 매시 정각 측정 인구(머문 시간/60분)의 월 합계다. 사람 수(명)나 시간대·야간 값이 아니다.
"""
import csv, json, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/open/population'
OUT = ROOT / 'data/population/jeju_emd_population_monthly.json'
DATASET = 'https://jejudatahub.net/data/view/data/748'
# 데이터허브 파일 ID → 저장 이름(연도)
FILES = [(2260, '2017'), (2258, '2018'), (2259, '2019'), (2515, '2020'), (2261, '2021')]
FIELDS = {'resident': '거주인구', 'worker': '근무인구', 'visitor': '방문인구'}


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    for file_id, label in FILES:
        path = RAW / f'jeju_emd_population_card_{label}.csv'
        if not path.exists():
            with urlopen(f'https://jejudatahub.net/api/file?id={file_id}', timeout=60) as response:
                path.write_bytes(response.read())
    return [RAW / f'jeju_emd_population_card_{label}.csv' for _, label in FILES]


def read_rows(path):
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return list(csv.DictReader(raw.decode(encoding).splitlines()))
        except UnicodeDecodeError:
            continue
    raise ValueError(f'{path.name}: 문자 형식을 읽지 못했습니다.')


MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def month_of(text):
    """'2018-01-01' 과 2021년 파일의 '21-Apr' 를 '2018-01' 꼴로 맞춘다."""
    text = text.strip()
    if text[:4].isdigit():
        return text[:7]
    year, name = text.split('-')
    return f'20{int(year):02d}-{MONTHS[name]:02d}'


def build(paths):
    per_gender = {}
    for path in paths:
        for row in read_rows(path):
            if row['성별'] not in ('남성', '여성'):
                continue  # 법인 줄은 인구 값이 없다(2021년 파일)
            key = (month_of(row['년월']), row['시도명'], row['읍면동명'], row['성별'])
            values = tuple(float(row[FIELDS[k]]) for k in ('resident', 'worker', 'visitor'))
            if per_gender.setdefault(key, values) != values:
                raise ValueError(f'{key}: 같은 월·읍면동·성별에 인구 값이 둘 이상입니다.')
    totals = defaultdict(lambda: [0.0, 0.0, 0.0])
    cities = {}
    for (month, city, dong, _gender), values in per_gender.items():
        cities[dong] = city
        for i, value in enumerate(values):
            totals[(dong, month)][i] += value
    months = sorted({month for _, month in totals})
    regions = []
    for dong in sorted(cities, key=lambda d: (cities[d], d)):
        regions.append({'name': dong, 'city': cities[dong],
                        'values': {m: [round(v) for v in totals[(dong, m)]] for m in months if (dong, m) in totals}})
    return {
        'source': {'title': '제주특별자치도_주제3_상권분석을 위한 유동인구에 따른 카드 매출액 변화 데이터 활용_매쉬업결과',
                   'portal': '제주데이터허브', 'url': DATASET, 'owner': '제주특별자치도 미래성장과',
                   'note': '제주빅데이터센터 데이터 활용', 'files': [p.name for p in paths],
                   'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                   'license': '데이터허브 화면에 이용 조건 표기 없음(미확인)'},
        'fields': ['resident', 'worker', 'visitor'],
        'labels': {'resident': '거주인구', 'worker': '근무인구', 'visitor': '방문인구'},
        'unit_note': '매시 정각에 측정한 인구(머문 시간/60분)를 한 달 동안 더한 값입니다. 사람 수(명)가 아니며 시간대·야간 값도 아닙니다.',
        'months': months,
        'regions': regions,
    }


if __name__ == '__main__':
    paths = download() if '--offline' not in sys.argv else sorted(RAW.glob('jeju_emd_population_card_*.csv'))
    result = build(paths)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'months': len(result['months']), 'first': result['months'][0], 'last': result['months'][-1],
                      'regions': len(result['regions']), 'bytes': OUT.stat().st_size}, ensure_ascii=False))
