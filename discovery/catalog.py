import csv
import hashlib
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


class CatalogSearch:
    def __init__(self,encoder,table=None,vectors=None):
        self.encoder=encoder
        table=Path(table or ROOT/'review/p1_catalog_all_INTERNAL.csv')
        vectors=Path(vectors or ROOT/'data/processed/catalog_embeddings_INTERNAL.npy')
        with table.open(newline='') as f: self.rows=list(csv.DictReader(f))
        self.vectors=np.load(vectors,allow_pickle=False)
        if len(self.rows)!=len(self.vectors):
            raise ValueError('목록과 벡터의 버전이 다릅니다.')
        self.version=hashlib.sha256(table.read_bytes()+vectors.read_bytes()).hexdigest()[:16]

    def search(self,query,limit=10):
        if not query.strip():
            raise ValueError('검색할 주제를 적어 주세요.')
        if not 1<=limit<=40:
            raise ValueError('후보 수는 1~40개로 제한합니다.')
        query_vector=self.encoder.encode([query])[0]
        scores=self.vectors@query_vector
        top=np.argsort(-scores,kind='stable')[:limit]
        return {'status':'candidate_only','adopted':False,'catalog_version':self.version,
                'restriction':'내부 검토용. 원자료·사용 조건·시간/공간 단위 확인 전 지표로 채택하지 않음',
                'candidates':[{**self.rows[int(i)],'query_similarity':float(scores[i]),'approve':''} for i in top]}
