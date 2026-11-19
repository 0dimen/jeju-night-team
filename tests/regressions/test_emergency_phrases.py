import pytest
from agent.report import emergency_check
from agent.report.preview import preview_report

# 2026-11-20 QA에서 112 안내로 연결되지 않던 표현과, 긴급으로 잘못 막던 시설 제보.
MISSED_BEFORE = [
    '뒤에서 어떤 남자가 쫓아오는 것 같아 무서워',
    '도와주세요 누가 저를 붙잡았어요',
    '모르는 사람이 계속 쫓아와',
    '차에 치였어요',
    '누가 나를 미행하는 것 같아',
    '방금 성추행 당했어요',
    '강도 당했어요 가방 뺏겼어요',
    '골목에서 누가 나 때렸어',
    '술 취한 사람이 계속 시비 걸어요',
    '무서워요 지금 어떡해요',
    '스토킹 당하는 것 같아요',
    '누가 내 뒤를 밟고 있어',
    '남자 두 명이 길을 막고 안 비켜줘요',
    'help someone is following me',
]

NOT_EMERGENCY = [
    '쓰러진 표지판이 있어요',
    '가로등이 쓰러져 있어요',
    '나무가 쓰러져서 길을 막고 있어요',
    '공사 펜스가 앞을 막고 있어요',
    '강도 높은 운동하고 걸어갈 거야',
    '따라가기 쉬운 길 알려줘',
    '밤에 이 길 좀 무서워요 가로등이 어두워서',
    '보도에 박스가 쌓여서 차도로 내려가야 했어',
]


@pytest.mark.parametrize('text', MISSED_BEFORE)
def test_danger_phrases_show_emergency_guide(text):
    assert emergency_check(text)
    view = preview_report(text, {'facility': 'other', 'problem': 'other'})
    assert view['kind'] == 'emergency' and '112' in view['message'] and not view['stored']


@pytest.mark.parametrize('text', NOT_EMERGENCY)
def test_object_and_ambiguous_phrases_stay_reports(text):
    assert not emergency_check(text)


def test_fallen_person_is_still_emergency():
    for text in ('친구가 쓰러졌어요', '나무 옆에 사람이 쓰러져 있어요'):
        assert emergency_check(text)
