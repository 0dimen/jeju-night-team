"""Vercel FastAPI 진입점. 계산용 파생 자료만 서버에 포함한다."""
import os
from pathlib import Path
root=Path(__file__).resolve().parent
if (root/'runtime/facilities').is_dir():
    os.environ.setdefault('JEJU_COMPILED_DATA_DIR',str(root/'runtime/facilities'))
from agent.api import app
