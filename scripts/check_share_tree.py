"""Git에 넣을 파일 또는 전체 추적 파일을 검사한다. 값은 출력하지 않는다."""
import argparse
import io
import os
import stat
import tempfile
import zipfile
from pathlib import PurePosixPath
import re
import subprocess
import sys

KEYS=re.compile(rb'AIza[0-9A-Za-z_-]{25,}|sk-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,}')
PRIVATE=[('mo'+'a').encode(),('모'+'아').encode(),('/data/'+'work/').encode(),('CODEX_'+'THREAD_ID').encode(),('/art'+'ifacts/').encode()]

def check_zip(content):
    """압축 바이트 대신 안전하게 펼친 각 파일을 기존 규칙으로 검사한다."""
    previous=os.getcwd()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            items=archive.infolist()
            if not items or len(items)>2000 or sum(i.file_size for i in items)>200_000_000:
                return False
            if len({i.filename for i in items})!=len(items):return False
            for item in items:
                path=PurePosixPath(item.filename)
                mode=item.external_attr>>16
                if (not path.parts or path.is_absolute() or '..' in path.parts or '.git' in path.parts
                    or '\\' in item.filename or ':' in path.parts[0] or item.flag_bits&1
                    or item.file_size>50_000_000 or path.suffix.lower()=='.zip'
                    or stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):
                    return False
            with tempfile.TemporaryDirectory(prefix='jeju-share-zip-') as folder:
                archive.extractall(folder)
                subprocess.run(['git','init','-q',folder],check=True,timeout=15)
                subprocess.run(['git','-C',folder,'add','-f','--all'],check=True,timeout=30)
                os.chdir(folder)
                try:return check()
                finally:os.chdir(previous)
    except (OSError,ValueError,RuntimeError,zipfile.BadZipFile,subprocess.SubprocessError):
        return False


def check(staged=False):
    names=subprocess.check_output(['git','diff','--cached','--name-only','--diff-filter=ACMR','-z'] if staged else ['git','ls-files','-z']).decode().split('\0')
    failed=[];checked=0
    for name in filter(None,names):
        path=PurePosixPath(name)
        if any(p in path.parts for p in ('raw','cache','models','.venv')) or 'INTERNAL' in name or path.suffix.lower() in ('.env','.sqlite','.sqlite3','.db','.xlsx') or (path.name.startswith('.env') and path.name != '.env.example'):
            failed.append((name,'비공유 파일'));continue
        meta=subprocess.check_output(['git','ls-files','-s','--',name],text=True)
        if meta.startswith(('120000','160000')):failed.append((name,'링크 파일'));continue
        content=subprocess.check_output(['git','show',':'+name])
        if path.suffix.lower()=='.zip':
            if not check_zip(content):failed.append((name,'ZIP 내부 공유 검사'))
            checked+=1
            continue
        if path.name == '.env.example' and any(line.strip() and not line.lstrip().startswith(b'#') and not re.fullmatch(rb'[A-Z_][A-Z0-9_]*=\s*', line.strip()) for line in content.splitlines()):
            failed.append((name,'값이 있는 환경 설정 예시'))
        if KEYS.search(content):failed.append((name,'키 형식'))
        if path.suffix=='.pdf':
            try:
                from pypdf import PdfReader
                text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages).encode()
            except Exception:
                failed.append((name,'PDF 추출 검사 불가'));continue
        elif path.suffix in ('.png','.parquet'):text=b''
        else:text=content
        if any(p.lower() in text.lower() for p in PRIVATE):failed.append((name,'비공유 운영 표현'))
        checked+=1
    for name,reason in failed:print(name+': '+reason)
    print('checked='+str(checked)+' failures='+str(len(failed)))
    return not failed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--staged',action='store_true');a=p.parse_args();sys.exit(0 if check(a.staged) else 1)
