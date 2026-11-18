import ast
import csv
import json
from pathlib import Path
import pytest
from lexicon.sources.local_files import collect
from lexicon.methods.cooccurrence import compute
from lexicon.review import export
from lexicon.review.apply import apply
from lexicon.sources.rss import collect as rss_collect


def test_lexicon_is_independent_and_has_provenance(tmp_path):
    root=Path(__file__).resolve().parents[2]
    for path in (root/'lexicon').rglob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('agent','stubs'))
            elif isinstance(node,ast.Import):
                assert not any(x.name.startswith(('agent','stubs')) for x in node.names)
    items=list(collect(root/'data/news_input/SYNTHETIC_news.jsonl'))
    rows=compute(items)
    assert rows and all(r['approve']=='' and r['sentence_ids'] and r['source_count']>=1 for r in rows)
    export(rows,tmp_path/'candidates.csv')
    registry=tmp_path/'enums.yaml'
    registry.write_text('preferences:\n  cctv: [CCTV]\n  streetlight: [가로등]\n  activity: [사람]\n')
    original=registry.read_text()
    assert apply(tmp_path/'candidates.csv',registry)==[]
    assert registry.read_text()==original
    one=rows[0].copy(); one['approve']='승인'
    export([one],tmp_path/'approved.csv')
    added=apply(tmp_path/'approved.csv',registry)
    assert len(added)==1


def test_rss_requires_confirmed_reuse_conditions():
    with pytest.raises(ValueError,match='재사용'):
        list(rss_collect('https://example.invalid/rss'))


def test_local_source_does_not_keep_full_article(tmp_path):
    item={'id':'SYNTHETIC','title':'제목','summary':'요약','date':'2026-11-18',
          'source_url':'https://example.invalid','article_body':'전문은 저장하면 안 됨'}
    p=tmp_path/'input.jsonl'; p.write_text(json.dumps(item)+'\n')
    assert 'article_body' not in list(collect(p))[0]


@pytest.mark.parametrize('previous',[False,True])
def test_empty_collection_clears_stale_review_rows(tmp_path,previous):
    path=tmp_path/'SYNTHETIC_candidates.csv'
    if previous:
        path.write_text('enum,term,approve\ncctv,SYNTHETIC_오래된후보,yes\n')
    export([],path)
    assert path.exists()
    with path.open(newline='') as stream:
        reader=csv.DictReader(stream)
        assert list(reader)==[] and 'approve' in reader.fieldnames
    if previous:
        snapshots=list((tmp_path/'.history').glob('*.csv'))
        assert len(snapshots)==1
        assert 'SYNTHETIC_오래된후보,yes' in snapshots[0].read_text()
