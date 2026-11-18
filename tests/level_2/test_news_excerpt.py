from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.collect_targeted_news import short_record


def test_selected_news_saves_short_excerpt_and_provenance_only():
    html='''<h4 class="subject">SYNTHETIC CCTV 소식<br><span>부제</span></h4>
    <div class="table_info">등록일:2026.10.03.</div>
    <div class="hwp_editor_board_content"><script>NEVER_SAVE_SCRIPT</script>
    CCTV 시설 관련 합성 문장입니다. '''+'오래된전문 '*40+'''</div>
    <img alt="공공누리 제1유형">'''
    row,check=short_record(html,'https://example.invalid/SYNTHETIC',datetime(2026,11,18,tzinfo=ZoneInfo('Asia/Seoul')))
    assert row['date']=='2026-10-03' and check['kogl_type_1']
    assert len((row['title']+' '+row['summary']).split())<=25
    assert 'NEVER_SAVE_SCRIPT' not in str(row) and '오래된전문' not in row['summary']
    assert 'body' not in row and not row['synthetic']


def test_unclear_license_or_old_date_is_not_collected():
    now=datetime(2026,11,18,tzinfo=ZoneInfo('Asia/Seoul'))
    assert short_record('<h4 class="subject">SYNTHETIC</h4>','https://example.invalid',now)[0] is None
    html='<div class="table_info">2025.01.01.</div><img alt="공공누리 제1유형">'
    assert short_record(html,'https://example.invalid',now)[0] is None


def test_public_hwp_embedded_text_can_supply_the_short_excerpt():
    now=datetime(2026,11,18,tzinfo=ZoneInfo('Asia/Seoul'))
    html='''<h4 class="subject">SYNTHETIC CCTV 제목</h4>
    <div class="table_info">2026.10.03.</div><div id="hwpEditorBoardContent"></div>
    <script>{"paragraph":{"t":"CCTV 주변 시설을 설명하는 SYNTHETIC 공개 문장입니다."}}</script>
    <img alt="공공누리 제1유형">'''
    row,check=short_record(html,'https://example.invalid/SYNTHETIC',now)
    assert row['summary_available'] and row['text_extraction']=='embedded_hwp_text'
    assert 'CCTV' in row['summary'] and check['summary_available']
