def candidates(rows):
    """쉽게 쓸 표현과 피할 표현의 후보만 내보낸다. 자동 승인하지 않는다."""
    banned=('안전','위험','보장','촬영','감시')
    return [{'term':r['term'],'kind':'avoid_candidate' if any(x in r['term'] for x in banned) else 'plain_candidate',
             'evidence':r['sentence_ids'],'approve':''} for r in rows]
