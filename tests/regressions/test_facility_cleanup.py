import csv
from pathlib import Path
import pytest
from agent.data.facility_cleanup import prepare_facilities


def write(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['종류','설치목적','위도','경도','데이터기준일']);w.writeheader();w.writerows(rows)


def test_holds_swapped_missing_nonfinite_without_autofix(tmp_path):
    p=tmp_path/'lights.csv'
    write(p,[{'종류':'가로등','위도':a,'경도':b} for a,b in [('33.25','126.56'),('126.56','33.25'),('','126.56'),('NaN','126.56'),('35','126.56')]])
    before=p.read_bytes();result=prepare_facilities(p,source_name='시험',source_url='https://example.org',kind='light')
    assert p.read_bytes()==before
    assert result['summary']['candidate_rows']==1 and result['summary']['held_rows']==4
    assert result['summary']['automatic_axis_corrections']==0
    assert result['metadata']['operationally_adopted'] is False


def test_preserves_duplicates_dates_and_explicit_purpose(tmp_path):
    p=tmp_path/'cctv.csv'
    write(p,[{'설치목적':purpose,'위도':'33.25','경도':'126.56','데이터기준일':'20221215'} for purpose in ['생활방범','생활방범','교통단속']])
    result=prepare_facilities(p,source_name='시험',source_url='https://example.org',kind='cctv',include_purposes=['생활방범'])
    assert len(result['rows'])==2
    assert all(row['same_coordinate_row_count']==2 and row['basis_date']=='2022-12-15' for row in result['rows'])
    assert result['summary']['automatic_merges']==0
    with pytest.raises(ValueError):prepare_facilities(p,source_name='시험',source_url='https://example.org',kind='cctv')


def test_unknown_light_kind_not_silently_adopted_and_bad_date_not_replaced(tmp_path):
    p=tmp_path/'lights.csv'
    write(p,[{'종류':'','위도':'33.25','경도':'126.56'},{'종류':'보안등','위도':'33.25','경도':'126.56','데이터기준일':'2025-99-99'}])
    result=prepare_facilities(p,source_name='시험',source_url='https://example.org',kind='light')
    assert result['summary']['held_rows']==1
    assert result['rows'][0]['basis_date'] is None and result['rows'][0]['basis_date_invalid']
