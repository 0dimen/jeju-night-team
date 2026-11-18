import test from 'node:test';
import assert from 'node:assert/strict';
import {createPageConversation} from '../../client/page_conversation.mjs';
const point={name:'SYNTHETIC 위치',lat:33.5,lng:126.5};
const response=state=>({ok:true,json:async()=>({kind:'clarification',state})});

test('페이지 이탈·뒤로가기 복원은 빈 상태로 시작한다',async()=> {
  const target=new EventTarget(),requests=[];
  const controller=createPageConversation({target,fetchImpl:async(url,options)=> {
    const input=JSON.parse(options.body);requests.push(input);return response(input.state);
  }});
  controller.setLocations({destination:point});await controller.send('집으로');
  assert.equal(requests[0].state.request.destination.name,point.name);
  target.dispatchEvent(new Event('pagehide'));
  await assert.rejects(controller.send('계속'));
  target.dispatchEvent(new Event('pageshow'));await controller.send('집으로');
  assert.deepEqual(requests[1].state,{});controller.dispose();
});

test('늦은 응답은 지운 위치를 되살리지 못한다',async()=> {
  let resolveFirst;const requests=[];let first=true;
  const controller=createPageConversation({target:new EventTarget(),fetchImpl:(url,options)=> {
    requests.push(JSON.parse(options.body));
    if(first) {first=false;return new Promise(resolve=>resolveFirst=resolve);}
    return Promise.resolve(response({}));
  }});
  controller.setLocations({destination:point});
  const waiting=controller.send('3시');controller.clear();
  resolveFirst(response({request:{destination:point}}));
  assert.equal(await waiting,null);await controller.send('다시');
  assert.deepEqual(requests[1].state,{});controller.dispose();
});

test('새 컨트롤러는 이전 위치를 상속하지 않는다',async()=> {
  const requests=[];const fetchImpl=async(url,options)=> {requests.push(JSON.parse(options.body));return response({});};
  const one=createPageConversation({target:new EventTarget(),fetchImpl});one.setLocations({destination:point});one.dispose();
  const two=createPageConversation({target:new EventTarget(),fetchImpl});await two.send('집으로');
  assert.deepEqual(requests[0].state,{});two.dispose();
});

test('화면 응답에는 위치 상태를 돌려주지 않는다',async()=> {
  const controller=createPageConversation({target:new EventTarget(),fetchImpl:async()=>response({request:{destination:point}})});
  assert.equal('state' in await controller.send('확인'),false);controller.dispose();
});

test('dispose 이후 요청은 보내지 않는다',async()=> {
  let calls=0;const controller=createPageConversation({target:new EventTarget(),fetchImpl:async()=> {calls++;return response({});}});
  controller.dispose();await assert.rejects(controller.send('집'));assert.equal(calls,0);
});
