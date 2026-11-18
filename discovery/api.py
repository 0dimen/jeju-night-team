"""프런트엔드 대신 자동 API 문서로 후보·실험 표를 확인한다. 내부 로컬 실행용."""
from functools import lru_cache
from fastapi import HTTPException
from pydantic import BaseModel,Field,field_validator
from agent.api import app
from agent.report import mask_personal_info
from discovery.catalog import CatalogSearch
from discovery.results import experiment_summaries


class CandidateBody(BaseModel):
    query:str=Field(min_length=1,max_length=300)
    limit:int=Field(default=10,ge=1,le=40)

    @field_validator('query')
    @classmethod
    def nonblank_query(cls,value):
        if not value.strip():
            raise ValueError('검색할 주제를 적어 주세요.')
        return value.strip()


@lru_cache(maxsize=1)
def catalog():
    from agent.intent.embedding import SentenceEncoder
    return CatalogSearch(SentenceEncoder())


@app.post('/data/candidates')
def candidates(body:CandidateBody):
    try:
        return catalog().search(mask_personal_info(body.query)[0],body.limit)
    except FileNotFoundError as exc:
        raise HTTPException(503,'목록·벡터 파일을 먼저 준비해야 합니다.') from exc


@app.get('/experiments/results')
def results():
    return experiment_summaries()
