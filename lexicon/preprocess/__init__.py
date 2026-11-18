import re
import unicodedata

SEEDS={'cctv':['cctv','카메라','감시'], 'streetlight':['가로등','보안등','불빛','어두운','컴컴'],
       'activity':['인적','귀갓길','보행','사람']}


def sentences(text):
    return [s.strip() for s in re.split(r'[.!?\n]+',text) if s.strip()]


def terms(text):
    text=unicodedata.normalize('NFKC',text).lower()
    # 외부 형태소 분석기 없이 표면형을 추출한다. 명사 분석이라고 부르지 않는다.
    return [x for x in re.findall(r'[가-힣a-z]{2,}',text) if x not in ('합성','뉴스','synthetic')]
