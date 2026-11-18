"""SYNTHETIC 연락처의 추가 표기. 실제 개인 번호가 아니다."""
import pytest
from agent.report import mask_personal_info
from stubs.reports import ReportStore

@pytest.mark.parametrize('text',[
 '070-0000-0000', '0507-0000-0000', '(010) 0000-0000',
 '010  0000  0000', '010\n0000\n0000', '+82 (0)10-0000-0000',
])
def test_R10_additional_contact_forms_are_masked(text):
 masked,changed=mask_personal_info('SYNTHETIC 가로등 꺼짐 '+text)
 assert changed and '[개인정보 가림]' in masked
 assert '0000' not in masked

def test_R10_new_forms_are_not_written_to_sqlite(tmp_path):
 store=ReportStore(tmp_path/'reports.sqlite')
 result=store.create('SYNTHETIC 가로등 꺼짐 070-0000-0000',33.5,126.5)
 assert result['classification']['personal_info_masked']
 store.close()
 assert b'070-0000-0000' not in (tmp_path/'reports.sqlite').read_bytes()
