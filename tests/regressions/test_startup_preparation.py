"""준비 확인의 한 번 호출·취소·실패 격리와 숫자 계측 계약."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from agent.api import app


def test_search_timings_are_numeric_and_private_on_success_and_failure(monkeypatch):
    import agent.maps.search as search
    client = TestClient(app)
    monkeypatch.setattr(search, 'search_places', lambda *args: [])
    good = client.post('/maps/places/search', json={'query': 'SYNTHETIC 개인 위치'})
    assert good.status_code == 200
    def unavailable(*args):
        raise search.SearchUnavailable('DO-NOT-ECHO')
    monkeypatch.setattr(search, 'search_places', unavailable)
    bad = client.post('/maps/places/search', json={'query': 'SYNTHETIC 개인 위치'})
    assert bad.status_code == 503
    for response in (good, bad):
        header = response.headers['Server-Timing']
        assert re.fullmatch(r'search;dur=\d+\.\d{2}, handler;dur=\d+\.\d{2}, init;dur=\d+\.\d{2}', header)
        assert response.headers['Cache-Control'] == 'no-store'
        assert 'DO-NOT-ECHO' not in response.text
    asset = client.get('/app/prepare.mjs')
    assert asset.status_code == 200 and 'createPreparation' in asset.text
    assert asset.headers['Cache-Control'] == 'no-store'


def test_preparation_runs_once_and_abort_and_failure_do_not_block():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    module = (Path(__file__).resolve().parents[2] / 'client/nightway/prepare.mjs').as_uri()
    script = '''
import assert from 'node:assert/strict';
import {createPreparation} from MODULE;
let calls = 0, finish;
const prepare = createPreparation(async (url, options) => {
  calls++;
  assert.equal(url, '/health');
  assert.equal(options.method, 'GET');
  assert.equal(options.credentials, 'omit');
  assert.equal(options.cache, 'no-store');
  assert.equal(options.body, undefined);
  return await new Promise(resolve => {finish=resolve});
});
const first = prepare();
assert.equal(calls, 1);
assert.equal(prepare(), first);
// 準備が未完了でも呼び出し元は別操作を続行できる。
let interactive = true; assert.equal(interactive, true);
finish({ok:true}); assert.equal(await first, true);
assert.equal(prepare(), first); assert.equal(calls,1);
let failures=0;
const failure=createPreparation(async()=>{failures++;throw new Error('offline')});
assert.equal(await failure(),false); assert.equal(await failure(),false);
assert.equal(failures,1);
const aborted=new AbortController();aborted.abort();
const never=createPreparation(async()=>{throw new Error('must not fetch')});
assert.equal(await never(aborted.signal),false);
let observedAbort=false;
const timed=createPreparation((url,{signal})=>new Promise((resolve,reject)=>{
 signal.addEventListener('abort',()=>{observedAbort=true;reject(new Error('abort'))});
}),5);
assert.equal(await timed(),false);assert.equal(observedAbort,true);
'''.replace('MODULE', repr(module)).replace('// 準備が未完了でも呼び出し元は別操作を続行できる。','// 준비가 끝나기 전에도 다른 조작을 계속할 수 있다.')
    completed = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
