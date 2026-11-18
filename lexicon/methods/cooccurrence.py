from collections import Counter
from math import log2
from lexicon.preprocess import terms,sentences,SEEDS


def compute(items,min_sources=1):
    documents=[]; counts=Counter(); pairs=Counter(); evidence={}; sources={}
    for item in items:
        for index,sentence in enumerate(sentences(item['title']+'. '+item['summary'])):
            tokens=set(terms(sentence))
            sid=item['id']+':'+str(index)
            documents.append(tokens)
            counts.update(tokens)
            for enum,seeds in SEEDS.items():
                if any(seed in sentence.lower() for seed in seeds):
                    pairs.update((enum,token) for token in tokens)
                    for token in tokens:
                        evidence.setdefault((enum,token),[]).append((sid,sentence))
                        sources.setdefault((enum,token),set()).add(item['source_url'])
    n=max(1,len(documents)); enum_counts={key:sum(any(seed in ' '.join(tokens) for seed in seeds) for tokens in documents) for key,seeds in SEEDS.items()}
    rows=[]
    for (enum,term),together in pairs.items():
        if term in SEEDS[enum] or len(sources[(enum,term)])<min_sources:
            continue
        score=log2((together*n)/(max(1,enum_counts[enum])*counts[term]))
        examples=evidence[(enum,term)][:2]
        rows.append({'enum':enum,'term':term,'score':score,'method':'sentence_pmi_surface',
                     'source_count':len(sources[(enum,term)]),'sentence_ids':';'.join(e[0] for e in examples),
                     'example_1':examples[0][1],'example_2':examples[1][1] if len(examples)>1 else '',
                     'source_urls':';'.join(sorted(sources[(enum,term)])),'approve':''})
    return sorted(rows,key=lambda r:(r['enum'],-r['score'],r['term']))
