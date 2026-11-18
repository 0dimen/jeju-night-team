from contextlib import nullcontext
import pytest


@pytest.fixture(autouse=True)
def isolate_mock_locks(monkeypatch):
    # 오프라인 mock 검사는 같은 기기의 실제 실험 잠금을 기다리지 않는다.
    monkeypatch.setattr('agent.llm.providers.gemini_rate_lock',nullcontext)
    monkeypatch.setattr('agent.llm.providers.model_lock',nullcontext)
