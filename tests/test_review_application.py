import csv
from pathlib import Path
import pytest
import yaml
from scripts.apply_review import apply


def write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def test_empty_approval_does_not_change_config(tmp_path):
    source=tmp_path/'review.csv';target=tmp_path/'settings.yaml'
    write(source,[{'decision':'P5','option':'50m','config_patch':'{"radius":50}','approve':''}])
    assert not apply(source,target)['written']
    assert not target.exists()


def test_only_approved_patch_is_exported(tmp_path):
    source=tmp_path/'review.csv';target=tmp_path/'settings.yaml'
    write(source,[{'decision':'P5','option':'30m','config_patch':'{"radius":30}','approve':'승인'},
                  {'decision':'P6','option':'Gemini','config_patch':'{"provider":"gemini"}','approve':''}])
    assert apply(source,target)['written']
    config=yaml.safe_load(target.read_text())
    assert config['radius']==30 and config['provider']=='none'


def test_conflicting_approvals_stop_before_writing(tmp_path):
    source=tmp_path/'review.csv';target=tmp_path/'settings.yaml'
    write(source,[{'decision':'P5','option':x,'config_patch':'{"radius":30}','approve':'yes'} for x in ('30m','50m')])
    with pytest.raises(ValueError):apply(source,target)
    assert not target.exists()


def test_different_decisions_cannot_silently_override_each_other(tmp_path):
    source=tmp_path/'review.csv';target=tmp_path/'settings.yaml'
    write(source,[{'decision':'P3','option':'규칙','config_patch':'{"intent":"I1"}','approve':'yes'},
                  {'decision':'P6','option':'모델','config_patch':'{"intent":"I3"}','approve':'yes'}])
    with pytest.raises(ValueError):apply(source,target)
    assert not target.exists()


@pytest.mark.parametrize('patch',[
    '{"radius":-1}', '{"radius":true}', '{"radius":NaN}',
    '{"threshold":2}', '{"intent":["I1"]}', '{"provider":"unknown"}',
    '{"duplicate_mode":"automatic_merge"}', '{"selected_catalog":"510"}',
    '{"provider":"gemini","model":"gemini-3.5-flash-lite","data_scope":"private"}',
])
def test_bad_approved_config_does_not_replace_existing_file(tmp_path,patch):
    source=tmp_path/'review.csv';target=tmp_path/'settings.yaml';target.write_text('SYNTHETIC existing')
    write(source,[{'decision':'P5','option':'합성 오류','config_patch':patch,'approve':'yes'}])
    with pytest.raises(ValueError):apply(source,target)
    assert target.read_text()=='SYNTHETIC existing'
    assert not target.with_suffix('.approval.json').exists()
