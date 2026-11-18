from pathlib import Path
import hashlib
import json
import re
import unicodedata
import math
from datetime import datetime

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
INDICATOR_NAMES={'cctv':'CCTV','streetlight':'가로등·보안등','activity':'과거 지역 활동'}


def load_yaml(path):
    return yaml.safe_load((ROOT / path).read_text(encoding='utf-8'))


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def check_schema(name, value):
    schema = json.loads((ROOT / 'contracts' / f'{name}.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(value)
    def finite_values(item):
        if isinstance(item,float) and not math.isfinite(item):
            raise ValueError('유한한 숫자만 허용합니다.')
        if isinstance(item,dict):
            for v in item.values(): finite_values(v)
        elif isinstance(item,list):
            for v in item: finite_values(v)
    finite_values(value)
    if name in ('route_request','facility_change'):
        timestamp=value['departure' if name=='route_request' else 'verified_at']
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?',timestamp):
            raise ValueError('날짜와 시각 형식을 확인하세요.')
        datetime.fromisoformat(timestamp)
    return value


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if c.isalnum()).lower()
