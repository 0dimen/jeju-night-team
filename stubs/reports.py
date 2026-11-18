"""SQLite 제보 대역. 원문을 가리고 검증 후 게시 이벤트만 엔진에 전달한다."""
from functools import wraps
from math import isfinite
from numbers import Real
from threading import RLock
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from agent.common import check_schema
from agent.report import classify, mask_personal_info,safe_report_summary

TRANSITIONS = {'DRAFT': {'SUBMITTED'}, 'SUBMITTED': {'AI_CLASSIFIED'},
               'AI_CLASSIFIED': {'UNDER_REVIEW'}, 'UNDER_REVIEW': {'VERIFIED', 'REJECTED'},
               'VERIFIED': {'PUBLISHED'}, 'REJECTED': set(), 'PUBLISHED': set()}


class ClassificationLockedError(ValueError):
    """검토가 끝난 분류는 늦은 모델 응답으로 바꾸지 않는다."""


def serialized(function):
    @wraps(function)
    def call(self,*args,**kwargs):
        with self.lock:
            return function(self,*args,**kwargs)
    return call


class ReportStore:
    def __init__(self,path=':memory:'):
        self.lock=RLock()
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, text TEXT NOT NULL,
            lat REAL, lng REAL, classification TEXT NOT NULL, status TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS history(seq INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT REFERENCES reports(id), before_state TEXT, after_state TEXT,
            actor TEXT, reason TEXT, at TEXT);
          CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT UNIQUE REFERENCES reports(id), payload TEXT NOT NULL);
        ''')

    @serialized
    def create(self,text,lat,lng,user_choice=None):
        if any(isinstance(x,bool) or not isinstance(x,Real) or not isfinite(x) for x in (lat,lng)):
            raise ValueError('위치는 유한한 숫자여야 합니다.')
        if not (-90<=lat<=90 and -180<=lng<=180):
            raise ValueError('위치 범위를 확인하세요.')
        result=classify(text,user_choice)
        rid='SYNTHETIC-RPT-'+uuid.uuid4().hex[:12]
        with self.db:
            self.db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?)',
                (rid,result['summary'],lat,lng,json.dumps(result,ensure_ascii=False),'DRAFT'))
            for state in ('SUBMITTED','AI_CLASSIFIED','UNDER_REVIEW'):
                self._move(rid,state,'agent','자동 접수; 검증 전')
        return self.get(rid)

    @serialized
    def get(self,rid):
        row=self.db.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
        if row is None: raise KeyError(rid)
        output=dict(row)
        output['classification']=json.loads(output['classification'])
        output['indicator_status']='confirmed' if output['status'] in ('VERIFIED','PUBLISHED') else (
            None if output['status']=='REJECTED' else 'pending')
        return output

    def _move(self,rid,after,actor,reason,allow_publish=False):
        if not isinstance(actor,str) or not isinstance(reason,str):
            raise ValueError('담당자와 근거를 적어야 합니다.')
        actor,_=mask_personal_info(actor);reason,_=mask_personal_info(reason)
        if not actor.strip() or not reason.strip():
            raise ValueError('담당자와 근거를 적어야 합니다.')
        before=self.get(rid)['status']
        if after not in TRANSITIONS[before]:
            raise ValueError(f'허용하지 않는 상태 전이: {before} → {after}')
        if after=='PUBLISHED' and not allow_publish:
            raise ValueError('시설 변경 이벤트와 함께 publish로 게시해야 합니다.')
        self.db.execute('UPDATE reports SET status=? WHERE id=?',(after,rid))
        self.db.execute('INSERT INTO history(report_id,before_state,after_state,actor,reason,at) VALUES(?,?,?,?,?,?)',
            (rid,before,after,actor,reason,datetime.now(timezone.utc).isoformat()))

    @serialized
    def transition(self,rid,after,actor,reason):
        with self.db:
            self._move(rid,after,actor,reason)
        return self.get(rid)

    @serialized
    def publish(self,rid,facility_id,facility_type,before,after,actor,reason):
        if self.get(rid)['status']!='VERIFIED':
            raise ValueError('검증한 제보만 게시할 수 있습니다.')
        actor,_=mask_personal_info(actor)
        if not actor.strip() or not isinstance(reason,str) or not reason.strip():
            raise ValueError('담당자와 근거를 적어야 합니다.')
        change=dict(facility_id=facility_id,type=facility_type,before=before,after=after,
                    report_id=rid,verified_by=actor,verified_at=datetime.now(timezone.utc).isoformat())
        check_schema('facility_change',change)
        prior=[e for e in self.published_changes() if e['facility_id']==facility_id]
        if prior and (prior[-1]['after']!=before or prior[-1]['type']!=facility_type):
            raise ValueError('마지막으로 게시한 시설 상태·유형과 일치하지 않습니다.')
        with self.db:
            self.db.execute('INSERT INTO changes(report_id,payload) VALUES(?,?)',
                            (rid,json.dumps(change,ensure_ascii=False)))
            self._move(rid,'PUBLISHED',actor,reason,allow_publish=True)
        return change

    @serialized
    def update_classification(self,rid,classification):
        check_schema('report_classification',classification)
        # 경로·모델에 관계없이 저장 직전에 한 번 더 가린다.
        summary,masked=mask_personal_info(classification['summary'])
        classification={**classification,'summary':safe_report_summary(summary),
                        'personal_info_masked':classification['personal_info_masked'] or masked}
        with self.db:
            cursor=self.db.execute('UPDATE reports SET classification=? WHERE id=? '
                "AND status IN ('DRAFT','SUBMITTED','AI_CLASSIFIED','UNDER_REVIEW')",
                (json.dumps(classification,ensure_ascii=False),rid))
            if cursor.rowcount!=1:
                self.get(rid)  # 없는 제보와 검토가 끝난 제보를 구별한다.
                raise ClassificationLockedError('검토가 끝난 분류는 새 제보·검토로 수정해야 합니다.')
        return self.get(rid)

    @serialized
    def published_changes(self):
        return [json.loads(r['payload']) for r in self.db.execute(
            'SELECT c.payload FROM changes c JOIN reports r ON r.id=c.report_id WHERE r.status=? ORDER BY c.seq',('PUBLISHED',))]

    @serialized
    def close(self):
        self.db.close()
