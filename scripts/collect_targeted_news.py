"""최근6개월 안의 주제 검색 선택표본. 제목·발췌만 저장하고 전문은 저장하지 않는다."""
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from time import sleep
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lexicon.preprocess import SEEDS,sentences

IDS=(126437,126820,128442,128476,129231,130820)
BASE='https://www.mois.go.kr/frt/bbs/type010/commonSelectBoardArticle.do'


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.body_depth=None;self.info_depth=None
        self.in_title=False;self.ignored=0;self.title=[];self.info=[];self.body=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.ignored+=1
        if tag=='div':
            self.depth+=1
            if 'hwp_editor_board_content' in a.get('class','') and self.body_depth is None:self.body_depth=self.depth
            if 'table_info' in a.get('class',''):self.info_depth=self.depth
        if tag=='h4' and 'subject' in a.get('class',''):self.in_title=True
        if tag=='br' and self.in_title:self.in_title=False
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.ignored=max(0,self.ignored-1)
        if tag=='h4':self.in_title=False
        if tag=='div':
            if self.body_depth==self.depth:self.body_depth=None
            if self.info_depth==self.depth:self.info_depth=None
            self.depth-=1
    def handle_data(self,data):
        if self.ignored:return
        if self.in_title:self.title.append(data)
        if self.body_depth is not None:self.body.append(data)
        if self.info_depth is not None:self.info.append(data)


def short_record(html,url,now):
    parser=ArticleParser();parser.feed(html)
    permitted=bool(re.search(r'alt="공공누리 제\s*1유형"',html))
    date=re.search(r'(\d{4})\.(\d{2})\.(\d{2})',' '.join(parser.info))
    if not permitted or not date:return None,{'url':url,'kogl_type_1':permitted,'date_found':bool(date)}
    at=datetime.strptime('-'.join(date.groups()),'%Y-%m-%d').date()
    if not 0<=(now.date()-at).days<=183:return None,{'url':url,'kogl_type_1':True,'date':at.isoformat(),'within_183_days':False}
    title=' '.join(' '.join(parser.title).split());title_words=title.split()[:15]
    budget=max(0,25-len(title_words));summary=''
    seeds=[seed for values in SEEDS.values() for seed in values]
    body=' '.join(parser.body);extraction='visible_html'
    if not any(seed in body.lower() for seed in seeds) and 'hwpEditorBoardContent' in html:
        # 공식 페이지의 한글 문서 렌더러에 들어 있는 공개 텍스트만 읽는다.
        # JavaScript를 실행하거나 첨부파일·전체 본문을 저장하지 않는다.
        parts=[]
        for raw in re.findall(r'"t"\s*:\s*("(?:\\.|[^"\\])*")',html):
            try:parts.append(json.loads(raw))
            except ValueError:continue
        body=' '.join(parts);extraction='embedded_hwp_text'
    for sentence in sentences(body):
        if not any(seed in sentence.lower() for seed in seeds):continue
        words=sentence.split();hit=next((i for i,w in enumerate(words) if any(seed in w.lower() for seed in seeds)),0)
        start=max(0,hit-budget//2) if len(words)>budget else 0
        summary=' '.join(words[start:start+budget]);break
    record={'id':'PUBLIC-MOIS-SELECTED-'+hashlib.sha256(url.encode()).hexdigest()[:12],
        'title':' '.join(title_words),'summary':summary,'date':at.isoformat(),'source_url':url,
        'source':'행정안전부 보도자료·주제 검색 선택표본','license':'공공누리 제1유형(출처표시)',
        'license_policy':'https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do',
        'summary_type':'제목과 주제 문장 발췌를 합쳐25어절이내. 전문·사진·첨부 저장 안 함',
        'text_extraction':extraction,'summary_available':bool(summary),'synthetic':False}
    assert len((record['title']+' '+record['summary']).split())<=25
    return record,{'url':url,'kogl_type_1':True,'date':at.isoformat(),'within_183_days':True,
                   'saved_word_count':len((record['title']+' '+record['summary']).split()),
                   'summary_available':bool(summary),'text_extraction':extraction}


def main():
    now=datetime.now(ZoneInfo('Asia/Seoul'));rows=[];checks=[]
    with httpx.Client(timeout=20,headers={'User-Agent':'JejuNightResearchBot/0.1'}) as client:
        rules=client.get('https://www.mois.go.kr/robots.txt');rules.raise_for_status()
        robots=RobotFileParser();robots.parse(rules.text.splitlines())
        for identifier in IDS:
            request=client.build_request('GET',BASE,params={'bbsId':'BBSMSTR_000000000008','nttId':identifier})
            url=str(request.url)
            if not robots.can_fetch('JejuNightResearchBot',url):
                checks.append({'url':url,'robots_allowed':False});continue
            sleep(1)
            response=client.send(request)
            if response.status_code!=200:
                checks.append({'url':url,'http_status':response.status_code});continue
            row,check=short_record(response.text,url,now);checks.append({**check,'http_status':200,'robots_allowed':True})
            if row:rows.append(row)
    target=ROOT/'data/news_input/PUBLIC_mois_topic_selected.jsonl'
    target.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    previous=[json.loads(s) for s in (ROOT/'data/news_input/PUBLIC_mois_recent.jsonl').read_text().splitlines()]
    combined=list({row['source_url']:row for row in previous+rows}.values())
    (ROOT/'data/news_input/PUBLIC_mois_selected_6m.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in combined))
    audit={'checked_at':now.isoformat(),'saved_selected':len(rows),'combined_items':len(combined),
        'selected_dates':sorted({r['date'] for r in rows}),'checks':checks,'article_body_saved':False,
        'selection':'CCTV·보행·도로 주제 검색에서 고른6개 원문. 검색 편향이 있으며6개월 전체 아카이브가 아님',
        'rights':'robots와각원문의공공누리제1유형을확인. 출처·날짜·허용조건과제목/짧은발췌만저장'}
    (ROOT/'experiments/results/human_evidence/public_topic_news_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
