"""운영체제별 파일 잠금. 잠금 파일은 지우지 않아 대기 중인 프로세스를 보호한다."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
from tempfile import gettempdir
from time import sleep


def _windows_lock(handle, backend):
    # Windows는 실제 존재하는 첫 1바이트를 잠근다. 핸들 위치도 매번 맞춘다.
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b'\0')
        handle.flush()
    while True:
        handle.seek(0)
        try:
            backend.locking(handle.fileno(), backend.LK_NBLCK, 1)
            return
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            sleep(0.05)


@contextmanager
def process_lock(name, directory=None):
    if Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('잠금 이름에는 파일 이름만 사용할 수 있습니다.')
    path = Path(gettempdir() if directory is None else directory) / name
    # append는 기존 파일을 잘라내지 않는다. Linux에서는 기존 잠금 경로를 유지한다.
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            _windows_lock(handle, msvcrt)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
