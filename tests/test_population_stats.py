"""유동인구 집계: 실제 원본에서 만든 값만 내주고, 지어낸 값으로 대신하지 않는다."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from agent.api import app

ROOT = Path(__file__).resolve().parents[1]


def test_population_file_shape_and_source():
    data = json.loads((ROOT / 'data/population/jeju_emd_population_monthly.json').read_text(encoding='utf-8'))
    assert data['source']['url'].endswith('/748') and data['fields'] == ['resident', 'worker', 'visitor']
    assert data['months'][0] == '2017-01' and data['months'][-1] == '2021-05' and len(data['months']) == 53
    assert len(data['regions']) == 43 and {r['city'] for r in data['regions']} == {'제주시', '서귀포시'}
    assert '사람 수(명)가 아니며' in data['unit_note']
    for region in data['regions']:
        for values in region['values'].values():
            assert len(values) == 3 and all(isinstance(v, int) and v >= 0 for v in values)


def test_population_endpoint_serves_file():
    response = TestClient(app).get('/data/population')
    assert response.status_code == 200 and response.json()['months'][-1] == '2021-05'
