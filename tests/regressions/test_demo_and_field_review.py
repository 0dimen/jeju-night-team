import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agent.api import app
from agent.data.field_review import export_review


def test_demo_only_serves_fixed_local_assets():
    with TestClient(app) as client:
        for asset in ('/demo','/demo/demo.css','/demo/demo.mjs','/demo/page_conversation.mjs'):
            response=client.get(asset)
            assert response.status_code==200
            assert response.headers['cache-control']=='no-store'
            assert "connect-src 'self'" in response.headers['content-security-policy']
        assert client.get('/demo/requirements-base.txt').status_code==404


def test_field_review_does_not_invent_verification_or_change_input(tmp_path):
    path=Path('data/route_examples/SYNTHETIC_routes.geojson')
    before=path.read_bytes()
    result=export_review(path,tmp_path)
    assert path.read_bytes()==before
    assert result['onsite_verified_by_export'] is False
    with (tmp_path/'field_review.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    assert rows and len(rows)==result['review_segment_count']
    for row in rows:
        assert all(row[key]=='' for key in ('통행 가능 여부','횡단 지점','야간 밝기','공사·폐쇄','시설 현재 상태','확인 날짜·시각','근거'))


def test_field_review_rejects_invalid_input_before_writing(tmp_path):
    path=tmp_path/'bad.json';path.write_text('{}')
    output=tmp_path/'review'
    with pytest.raises(ValueError):export_review(path,output)
    assert not output.exists()


def test_field_review_preserves_existing_human_notes(tmp_path):
    path=Path('data/route_examples/SYNTHETIC_routes.geojson')
    export_review(path,tmp_path)
    note=tmp_path/'field_review.csv'
    note.write_text('사람이 적은 현장 메모',encoding='utf-8')
    with pytest.raises(FileExistsError):export_review(path,tmp_path)
    assert note.read_text(encoding='utf-8')=='사람이 적은 현장 메모'
