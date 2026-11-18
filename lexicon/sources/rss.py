"""제목·요약만 수집한다. 재사용 조건을 확인한 피드만 명시적으로 실행한다."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import hashlib
import xml.etree.ElementTree as ET
import httpx


def collect(url,terms_checked=False,days=183):
    if not terms_checked:
        raise ValueError('피드 재사용 조건 확인이 필요합니다.')
    parsed=urlsplit(url)
    if parsed.scheme!='https':
        raise ValueError('HTTPS 공개 피드만 사용합니다.')
    base=f'{parsed.scheme}://{parsed.netloc}'
    with httpx.Client(timeout=20,follow_redirects=True,headers={'User-Agent':'JejuNightResearchBot/0.1'}) as client:
        rules=client.get(base+'/robots.txt')
        if rules.status_code not in (200,404):
            raise ValueError('robots.txt 확인 실패')
        robot=RobotFileParser()
        robot.parse(rules.text.splitlines() if rules.status_code==200 else [])
        if not robot.can_fetch('JejuNightResearchBot',url):
            raise ValueError('피드 수집이 robots.txt에서 허용되지 않음')
        response=client.get(url)
        response.raise_for_status()
    root=ET.fromstring(response.content)
    now=datetime.now(timezone.utc)
    for item in root.findall('.//item'):
        title=item.findtext('title','').strip()
        summary=item.findtext('description','').strip()
        link=item.findtext('link','').strip()
        date=item.findtext('pubDate','')
        try:
            at=parsedate_to_datetime(date)
            if at.tzinfo is None:
                at=at.replace(tzinfo=timezone.utc)
        except (ValueError,TypeError):
            continue
        if not 0 <= (now-at).days <= days:
            continue
        yield {'id':hashlib.sha256(link.encode()).hexdigest()[:16],'title':title,
               'summary':summary[:600],'date':at.date().isoformat(),'source_url':link,'synthetic':False}
