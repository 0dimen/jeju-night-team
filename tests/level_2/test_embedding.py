import numpy as np
from agent.intent.embedding import PreferenceClassifier
from agent.intent.methods import interpret


class FixedEncoder:
    model_name='SYNTHETIC deterministic test vector'
    def encode(self,texts):
        vectors=[]
        for text in texts:
            if any(w in text for w in ('CCTV','시설이 있는')): v=[1,0,0,0]
            elif any(w in text for w in ('밝은','가로등')): v=[0,1,0,0]
            elif any(w in text for w in ('사람','인적')): v=[0,0,1,0]
            else: v=[0,0,0,1]
            vectors.append(v)
        return np.array(vectors,dtype=np.float32)


def test_embedding_gate_and_interface():
    classifier=PreferenceClassifier(FixedEncoder(),threshold=.62)
    result=interpret('밝은 경로',method='I2',embedding=classifier)
    assert result['request']['preferences']==['streetlight']
    assert result['method']=='embedding'
    assert classifier.classify('밝은 경로',threshold=1.1)['preferences']==[]


def test_missing_embedding_uses_rules():
    result=interpret('가로등 경로',method='I2')
    assert result['fallback_reason']=='embedding_unavailable'
