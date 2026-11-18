"""실제 프로세스 배타성 및 Windows 분기의 오류 처리를 검사한다."""
import errno
import os
from pathlib import Path
import subprocess
import sys

import pytest
from agent.file_lock import _windows_lock, process_lock


def test_processes_do_not_lose_updates(tmp_path):
    counter=tmp_path/'counter.txt';counter.write_text('0')
    code='''from pathlib import Path
from agent.file_lock import process_lock
import sys,time
folder=Path(sys.argv[1])
for _ in range(12):
    with process_lock('test.lock',folder):
        p=folder/'counter.txt';n=int(p.read_text());time.sleep(.002);p.write_text(str(n+1))
'''
    processes=[subprocess.Popen([sys.executable,'-c',code,str(tmp_path)]) for _ in range(3)]
    try:
        for p in processes:assert p.wait(timeout=20)==0
    finally:
        for p in processes:
            if p.poll() is None:p.kill();p.wait()
    assert counter.read_text()=='36'


def test_exception_releases_lock(tmp_path):
    with pytest.raises(RuntimeError):
        with process_lock('error.lock',tmp_path):raise RuntimeError('failed work')
    code='from agent.file_lock import process_lock; import sys\nwith process_lock("error.lock",sys.argv[1]): print("released")'
    assert subprocess.check_output([sys.executable,'-c',code,str(tmp_path)],timeout=5,text=True).strip()=='released'


def test_provider_import_does_not_require_fcntl():
    code='''import builtins
original=builtins.__import__
def blocked(name,*a,**k):
    if name=='fcntl':raise ImportError('Windows simulation')
    return original(name,*a,**k)
builtins.__import__=blocked
from agent.llm.providers import make_provider
assert make_provider().name=='none'
'''
    subprocess.run([sys.executable,'-c',code],check=True,timeout=15)


def test_windows_retry_and_byte_position(tmp_path,monkeypatch):
    class Backend:
        LK_NBLCK=2
        calls=0
        def locking(self,fd,mode,n):
            self.calls+=1
            assert os.lseek(fd,0,os.SEEK_CUR)==0 and n==1
            assert os.fstat(fd).st_size>=1
            if self.calls==1:raise OSError(errno.EACCES,'locked')
    backend=Backend();waits=[]
    monkeypatch.setattr('agent.file_lock.sleep',waits.append)
    with (tmp_path/'win.lock').open('a+b') as handle:_windows_lock(handle,backend)
    assert backend.calls==2 and waits==[.05]


def test_windows_unexpected_error_is_not_hidden(tmp_path):
    class Backend:
        LK_NBLCK=2
        def locking(self,*args):raise OSError(errno.EBADF,'bad handle')
    with (tmp_path/'win.lock').open('a+b') as handle:
        with pytest.raises(OSError) as error:_windows_lock(handle,Backend())
    assert error.value.errno==errno.EBADF


def test_korean_config_does_not_depend_on_default_encoding(monkeypatch):
    from agent.common import load_yaml, check_schema, ROOT
    original=Path.read_text
    def legacy_default(path,encoding=None,errors=None):
        return original(path,encoding=encoding or 'cp949',errors=errors)
    monkeypatch.setattr(Path,'read_text',legacy_default)
    assert load_yaml('registry/emergency_phrases.yaml')['message']
    from agent.orchestrator import NightAgent
    result=NightAgent().run('누가 따라와요')
    assert result['kind']=='emergency' and '112' in result['message']
