"""커밋한 실행 코드의 ZIP을 만들며 data/open이 제외됐는지 검사한다."""
import argparse
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--include-facility-data',action='store_true',help='원본 대신 서버용 공개 좌표 계산 자료 포함');args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():raise FileExistsError('기존 묶음을 보존합니다. 새 출력 이름을 지정하세요.')
    output.parent.mkdir(parents=True,exist_ok=True)
    if args.include_facility_data:
        subprocess.run([sys.executable,str(ROOT/'scripts/build_vercel_data.py')],cwd=ROOT,check=True)
    subprocess.run(['git','archive','--worktree-attributes','--format=zip','--output',str(output),'HEAD'],cwd=ROOT,check=True)
    if args.include_facility_data:
        with zipfile.ZipFile(output,'a',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ('yeondong_standard.json','yeondong_datahub.json','seogwipo_standard.json','seogwipo_datahub.json','jeju_facilities.json','build_info.json'):
                source=ROOT/'runtime/facilities'/name
                archive.write(source,'runtime/facilities/'+name)
    with zipfile.ZipFile(output) as archive:
        names=archive.namelist()
        if any(name=='data/open/' or name.startswith('data/open/') for name in names):
            output.unlink();raise RuntimeError('공개 원본이 묶음에 포함되어 생성을 취소했습니다.')
        if archive.testzip():raise RuntimeError('ZIP 무결성 검사 실패')
    print('배포 묶음 생성:',output.name,'항목:',len(names),'data/open 포함: 0')
