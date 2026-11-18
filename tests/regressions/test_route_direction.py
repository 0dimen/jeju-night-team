"""장소 언급 순서보다 명시된 출발·도착 조사를 따른다. 합성 장소 4개만 사용."""
import pytest
from agent.intent import parse
from agent.orchestrator import NightAgent


@pytest.mark.parametrize('text',[
    '탑동광장까지 제주시청에서 CCTV 길로 2026-11-18T22:00',
    '탑동광장으로 가려는데 제주시청에서 출발 2026-11-18T22:00',
    '제주공항은 말고 제주시청에서 탑동광장까지 2026-11-18T22:00',
])
def test_explicit_direction_is_preserved(text):
    request=parse(text)['request']
    assert request['origin']['name']=='제주시청'
    assert request['destination']['name']=='탑동광장'


def test_two_explicit_origins_require_clarification():
    result=NightAgent().run('제주시청에서 제주공항에서 탑동광장까지 2026-11-18T22:00')
    assert result['kind']=='clarification' and 'origin' in result['missing']


def test_two_explicit_destinations_require_clarification():
    result=NightAgent().run('제주시청에서 제주공항까지 탑동광장까지 2026-11-18T22:00')
    assert result['kind']=='clarification' and 'destination' in result['missing']
