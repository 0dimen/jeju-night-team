"""SYNTHETIC 원본으로 결측·과거 기준일·같은 좌표·대수의 구별을 검사한다."""
from datetime import date
from scripts.audit_cctv_source import audit


def test_source_audit_counts_rows_and_devices_separately(tmp_path):
    path=tmp_path/'SYNTHETIC_cctv.csv'
    path.write_text('위도,경도,데이터기준일,설치목적,카메라대수\n'
                    '33.5,126.5,20240101,SYNTHETIC 기타,4\n'
                    '33.5,126.5,20240729,SYNTHETIC 기타,2\n',encoding='cp949')
    result=audit(path,date(2026,11,18))
    assert result['rows']==2 and result['unique_coordinate_pairs']==1
    assert result['declared_camera_count']=={'status':'available','value':6}
    assert result['extra_rows_at_repeated_coordinates']==1
    assert result['latest_basis_date']=='2024-07-29'
    assert result['status']=='candidate_only' and not result['adopted']


def test_source_audit_missing_values_are_not_zero(tmp_path):
    path=tmp_path/'SYNTHETIC_missing.csv'
    path.write_text('위도,경도,데이터기준일,대수_미제공\n'
                    'nan,126.5,20260230,\n')
    result=audit(path,date(2026,11,18))
    assert result['invalid_or_missing_coordinates']==1
    assert result['invalid_or_missing_basis_dates']==1
    assert result['declared_camera_count']=={'status':'unavailable'}


def test_source_audit_ragged_row_counts_missing_date(tmp_path):
    path=tmp_path/'SYNTHETIC_short.csv'
    path.write_text('위도,경도,데이터기준일\n33.5,126.5\n')
    result=audit(path,date(2026,11,18))
    assert result['valid_global_coordinates']==1
    assert result['invalid_or_missing_basis_dates']==1
    assert result['declared_camera_count']=={'status':'unavailable'}
