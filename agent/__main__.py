import argparse
import json
from agent.orchestrator import NightAgent
from agent.common import ROOT
from agent.common import load_yaml
from agent.llm import make_provider

p = argparse.ArgumentParser()
p.add_argument('--demo', action='store_true')
p.add_argument('--text')
p.add_argument('--level',choices=['L0','L1','L2','L3'],default='L0')
p.add_argument('--config',help='experiments/configs/ 아래 설정 또는 저장소 상대 경로')
args = p.parse_args()
config=load_yaml(args.config) if args.config else load_yaml('config/levels.yaml')['levels'][args.level]
provider=make_provider(config) if config.get('provider','none')!='none' else None
embedding=None
if config.get('intent')=='I2':
    try:
        from agent.intent.embedding import SentenceEncoder,PreferenceClassifier
        embedding=PreferenceClassifier(SentenceEncoder(),config.get('threshold',.62))
    except Exception:
        pass  # 벡터 파일이 없으면 규칙 기반 해석으로 대체한다.
discovery=None
if config.get('discovery'):
    try:
        from agent.intent.embedding import SentenceEncoder
        from discovery.catalog import CatalogSearch
        discovery=CatalogSearch(embedding.encoder if embedding is not None else SentenceEncoder())
    except Exception:
        pass
agent = NightAgent(config,provider,embedding=embedding,discovery=discovery)
if args.demo:
    request = json.loads((ROOT/'contracts/examples/SYNTHETIC_route_request.json').read_text(encoding='utf-8'))
    result = agent.route(request)
else:
    result = agent.run(args.text or '제주시청에서 탑동광장까지 밝은 길로')
print(json.dumps(result, ensure_ascii=False, indent=2))
if provider is not None:
    provider.close()
