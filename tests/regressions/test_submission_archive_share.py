"""압축 파일은 내부 파일을 검사하고 경로 탈출·비밀 파일은 차단한다."""
import io
import zipfile
import pytest
from scripts.check_share_tree import check_zip


def archive(files):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
        for name,content in files.items():z.writestr(name,content)
    return output.getvalue()


def test_zip_binary_bytes_are_not_mistaken_for_text():
    # 기존 검사는 그림의 바이트도 운영 표현으로 오인했다.
    assert check_zip(archive({'project/picture.png':('mo'+'a').encode(),'project/README.md':b'public source'}))


@pytest.mark.parametrize('name',['../escape.txt','project/.env','project/nested.zip','/absolute.txt'])
def test_zip_rejects_unsafe_paths_settings_and_nested_archives(name):
    assert not check_zip(archive({name:b'not-a-real-secret'}))


def test_zip_inspects_private_text_inside_compression():
    assert not check_zip(archive({'project/README.md':('mo'+'a').encode()}))
