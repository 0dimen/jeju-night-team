"""고정된 다국어 ONNX 문장 벡터. 문자 유사도 대안과 구분한다."""
from pathlib import Path
import json
import os
import numpy as np
from agent.common import ROOT, load_yaml


class SentenceEncoder:
    model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    revision='e8f8c211226b894fcb81acc59f3b34ba3efd5f42'

    def __init__(self,path=None):
        path=Path(path or ROOT/'models/multilingual-minilm')
        required=(path/'onnx/model_qint8_arm64.onnx',path/'tokenizer.json')
        if not all(item.is_file() for item in required):
            raise FileNotFoundError('로컬 문장 벡터 모델·토크나이저가 준비되지 않았습니다.')
        os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
        import onnxruntime as ort
        ort.disable_telemetry_events()
        from tokenizers import Tokenizer
        options=ort.SessionOptions()
        options.intra_op_num_threads=2
        options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path/'onnx/model_qint8_arm64.onnx'),sess_options=options,
                                         providers=['CPUExecutionProvider'])
        self.tokenizer=Tokenizer.from_file(str(path/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding()

    def encode(self,texts,batch_size=24):
        outputs=[]
        for start in range(0,len(texts),batch_size):
            encoded=self.tokenizer.encode_batch(texts[start:start+batch_size])
            ids=np.array([e.ids for e in encoded],dtype=np.int64)
            mask=np.array([e.attention_mask for e in encoded],dtype=np.int64)
            types=np.array([e.type_ids for e in encoded],dtype=np.int64)
            fields={'input_ids':ids,'attention_mask':mask,'token_type_ids':types}
            feed={x.name:fields[x.name] for x in self.session.get_inputs()}
            raw=self.session.run(None,feed)[0]
            if raw.ndim==3:
                pooled=(raw*mask[:,:,None]).sum(axis=1)/np.maximum(mask.sum(axis=1,keepdims=True),1)
            else:
                pooled=raw
            pooled=pooled/np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-12)
            outputs.append(pooled.astype(np.float32))
        return np.concatenate(outputs) if outputs else np.empty((0,384),np.float32)


class PreferenceClassifier:
    def __init__(self,encoder,threshold=0.62):
        self.encoder,self.threshold=encoder,threshold
        self.labels=[]; self.examples=[]
        phrases={'cctv':['CCTV 카메라가 있는 경로','주변을 확인하는 시설이 있는 길'],
                 'streetlight':['가로등 불빛이 밝은 경로','어둡지 않은 밝은 길'],
                 'activity':['사람들이 많이 다니는 길','인적이 있는 경로'],
                 'none':['시설 선호 없이 가는 길','아무 경로나 상관없음']}
        for label,texts in phrases.items():
            for text in texts:
                self.labels.append(label); self.examples.append(text)
        self.vectors=encoder.encode(self.examples)

    def classify(self,text,threshold=None):
        threshold=self.threshold if threshold is None else threshold
        vector=self.encoder.encode([text])[0]
        sims=self.vectors@vector
        scores={label:float(max(sims[i] for i,l in enumerate(self.labels) if l==label)) for label in set(self.labels)}
        # 여러 선호는 각각 통과해야 한다. 기본 none은 다른 선호가 없을 때만 둔다.
        labels=[label for label in ('cctv','streetlight','activity') if scores[label]>=threshold]
        if not labels and scores['none']>=threshold:
            labels=['none']
        return {'preferences':labels,'scores':dict(sorted(scores.items())),
                'threshold':threshold,'model':self.encoder.model_name}
