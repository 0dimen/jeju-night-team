import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


@pytest.fixture
def request_data():
    return json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text())
