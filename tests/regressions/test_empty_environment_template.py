"""빈 환경 설정 양식만 허용하며 값이 있는 파일은 계속 차단한다."""
import subprocess
import pytest
from scripts.check_share_tree import check


@pytest.mark.parametrize('name,content,allowed', [
    ('.env.example', '# 값은 서버에서만 입력\nVWORLD_API_KEY=\n', True),
    ('.env.example', 'VWORLD_API_KEY=not-a-real-key\n', False),
    ('.env.production', 'VWORLD_API_KEY=\n', False),
])
def test_empty_template_does_not_allow_real_settings(tmp_path, monkeypatch, name, content, allowed):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    (tmp_path/name).write_text(content)
    subprocess.run(['git','-C',str(tmp_path),'add','--',name],check=True)
    monkeypatch.chdir(tmp_path)
    assert check(staged=True) is allowed
