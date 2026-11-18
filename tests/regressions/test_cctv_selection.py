import csv
from pathlib import Path
import pytest
import yaml
from agent.data.cctv import select


def fixtures(tmp_path,purposes=None,rights=False,coordinate=False):
    source=tmp_path/'source.csv';policy=tmp_path/'policy.yaml'
    with source.open('w',encoding='cp949',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['설치목적','위도','경도','데이터기준일','카메라대수'])
        w.writeheader()
        for purpose in ['생활방범','교통단속','어린이보호']:
            w.writerow({'설치목적':purpose,'위도':33.3,'경도':126.5,'데이터기준일':'20221215','카메라대수':4})
    policy.write_text(yaml.safe_dump({'version':'test','include_purposes':purposes or ['생활방범'],
        'rights_confirmed':rights,'coordinate_system_confirmed':coordinate},allow_unicode=True),encoding='utf-8')
    return source,policy


def test_selection_preserves_source_and_never_adds_other_purposes(tmp_path):
    source,policy=fixtures(tmp_path);original=source.read_bytes()
    result=select(source,policy)
    assert [r['purpose'] for r in result['rows']]==['생활방범']
    assert result['excluded_purpose_counts']=={'교통단속':1,'어린이보호':1}
    assert not result['ready_for_real_route_use'] and source.read_bytes()==original


def test_policy_changes_selection_without_changing_loader(tmp_path):
    source,policy=fixtures(tmp_path,['생활방범','어린이보호'])
    assert len(select(source,policy)['rows'])==2


@pytest.mark.parametrize('rights,coordinate',[(False,True),(True,False),('false',True)])
def test_partial_or_string_approval_is_not_ready(tmp_path,rights,coordinate):
    source,policy=fixtures(tmp_path,rights=rights,coordinate=coordinate)
    assert not select(source,policy)['ready_for_real_route_use']


def test_invalid_selected_coordinate_does_not_silently_disappear(tmp_path):
    source,policy=fixtures(tmp_path)
    source.write_bytes(source.read_bytes().replace(b'33.3',b'nan',1))
    with pytest.raises(ValueError):select(source,policy)
