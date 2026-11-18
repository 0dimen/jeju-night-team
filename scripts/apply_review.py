"""사람이 승인 표시한 결정만 별도 설정으로 내보낸다. 승인 자체를 만들지 않는다."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from math import isfinite
from numbers import Real
from pathlib import Path
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
APPROVED={'yes','y','true','1','승인'}


def validate_config(config):
    choices={'structure':{'S1','S2','S3'},'intent':{'I1','I2','I3','I4'},
             'explain':{'E1','E2','E3'},'provider':{'none','mock','ollama','gemini','openai','anthropic'},
             'data_scope':{'private','synthetic','public'},'duplicate_mode':{'candidate_only','off'},
             'ambiguity_policy':{'clarify','other_pending'},'lexicon_mode':{'hold','approved_only'}}
    for field,allowed in choices.items():
        if field in config and (not isinstance(config[field],str) or config[field] not in allowed):
            raise ValueError('설정의 허용 값을 확인해야 합니다: '+field)
    for field,lower,upper in [('radius',0,200),('threshold',-1,1),('duplicate_threshold',-1,1)]:
        if field not in config:continue
        value=config[field]
        if (isinstance(value,bool) or not isinstance(value,Real) or not isfinite(value)
                or not lower<=value<=upper or (field=='radius' and value==0)):
            raise ValueError('설정의 숫자 범위를 확인해야 합니다: '+field)
    if config['provider'] not in ('none','mock'):
        if not isinstance(config.get('model'),str) or not config['model'].strip():
            raise ValueError('실제 공급자는 모델 이름이 필요합니다.')
    if 'selected_catalog' in config:
        values=config['selected_catalog']
        if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError('목록 후보는 비어 있지 않은 이름 목록이어야 합니다.')
        if len(values)!=len(set(values)):
            raise ValueError('목록 후보가 중복되었습니다.')


def apply(path,out):
    path=Path(path);out=Path(out)
    if path.resolve()==out.resolve():
        raise ValueError('검토 원본과 출력 설정은 다른 파일이어야 합니다.')
    with path.open(newline='') as f:
        selected=[row for row in csv.DictReader(f) if row.get('approve','').strip().lower() in APPROVED]
    groups={}
    for row in selected:
        if row['decision'] in groups:
            raise ValueError('한 결정에서 여러 선택지를 승인했습니다: '+row['decision'])
        groups[row['decision']]=row
    if not groups:
        return {'status':'no_approved_rows','written':False}
    config={'structure':'S1','intent':'I1','explain':'E1','provider':'none','data_scope':'private',
            'radius':50,'duplicate_mode':'candidate_only','discovery':True}
    evidence=[];followups=[];explicit={}
    for decision,row in groups.items():
        patch=json.loads(row['config_patch'])
        if not isinstance(patch,dict):raise ValueError('설정 변경은 객체여야 합니다.')
        allowed={'provider','model','data_scope','structure','intent','explain','threshold','radius',
                 'duplicate_mode','duplicate_threshold','ambiguity_policy','selected_catalog','lexicon_mode'}
        if not set(patch)<=allowed: raise ValueError('허용하지 않는 설정 칸')
        for field,value in patch.items():
            if field in explicit and explicit[field]!=value:
                raise ValueError('서로 다른 결정에서 설정이 충돌했습니다: '+field)
            explicit[field]=value
        config.update(patch)
        evidence.append({'decision':decision,'option':row['option'],'source':str(path),
                         'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        if decision=='P1': followups.append('선택한 원자료의 좌표·기간·권리·지정 데이터 여부를 검증해야 채택 가능')
        if decision in ('P4','P7'): followups.append(decision+': 서비스의 후보 표시·확인 흐름 연결 필요. 자동 확정·병합 없음')
    validate_config(config)
    if config.get('provider')=='gemini':
        if config.get('data_scope') not in ('synthetic','public'):
            raise ValueError('무료 API는 합성·공개 시연에만 허용합니다.')
        followups.append('이 설정은 합성·공개 시연 전용. 실제 개인 위치·제보에 사용하지 않음')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
    record={'applied_at':datetime.now(timezone.utc).isoformat(),'source_approvals':evidence,
            'result_config':str(out),'followups':followups,
            'note':'설정 내보내기는 실제 원자료 검증·배포·사용자 수용을 뜻하지 않음'}
    out.with_suffix('.approval.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    return {'status':'exported_approved_rows','written':True,'decisions':list(groups),'followups':followups}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--review',default='review/decision_options.csv')
    p.add_argument('--out',default='config/approved_review.yaml')
    args=p.parse_args()
    print(json.dumps(apply(args.review,args.out),ensure_ascii=False))
