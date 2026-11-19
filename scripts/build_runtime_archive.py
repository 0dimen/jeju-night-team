"""커밋한 실행 코드의 ZIP을 만들며 data/open이 제외됐는지 검사한다."""
import argparse
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():raise FileExistsError('기존 묶음을 보존합니다. 새 출력 이름을 지정하세요.')
    output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','archive','--worktree-attributes','--format=zip','--output',str(output),'HEAD'],cwd=ROOT,check=True)
    with zipfile.ZipFile(output) as archive:
        names=archive.namelist()
        if any(name=='data/open/' or name.startswith('data/open/') for name in names):
            output.unlink();raise RuntimeError('공개 원본이 묶음에 포함되어 생성을 취소했습니다.')
        if archive.testzip():raise RuntimeError('ZIP 무결성 검사 실패')
    print('배포 묶음 생성:',output.name,'항목:',len(names),'data/open 포함: 0')
