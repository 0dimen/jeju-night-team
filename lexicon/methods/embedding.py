from lexicon.preprocess import SEEDS


def compare(rows,encoder):
    """encode(list[str])를 가진 외부 벡터 도구를 주입한다. 서비스 코드는 import하지 않는다."""
    if not rows:
        return []
    labels=list(SEEDS)
    bases=encoder.encode([' '.join(SEEDS[label]) for label in labels])
    terms=encoder.encode([r['term'] for r in rows])
    for row,vector in zip(rows,terms):
        row=dict(row)
        row['embedding_score']=float(vector@bases[labels.index(row['enum'])])
        yield row
