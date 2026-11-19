"""Git에 넣을 파일 또는 전체 추적 파일을 검사한다. 값은 출력하지 않는다."""
import argparse
import io
from pathlib import PurePosixPath
import re
import subprocess
import sys

KEYS=re.compile(rb'AIza[0-9A-Za-z_-]{25,}|sk-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,}')
PRIVATE=[('mo'+'a').encode(),('모'+'아').encode(),('/data/'+'work/').encode(),('CODEX_'+'THREAD_ID').encode(),('/art'+'ifacts/').encode()]

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
