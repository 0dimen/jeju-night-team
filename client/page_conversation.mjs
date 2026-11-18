/** 페이지 메모리만 쓰는 연결부. 실제 화면은 페이지 이동 때 dispose()를 호출한다. */
export function createPageConversation({fetchImpl=globalThis.fetch, target=globalThis.window, endpoint='/agent/conversation'}={}) {
  let state={}, sequence=0, pending=null, active=true, disposed=false;
  const clone=value=>structuredClone(value);
  function clear() {
    sequence++; state={}; pending?.abort(); pending=null;
  }
  function leave() { clear(); active=false; }
  function enter() { if(!disposed) { clear(); active=true; } }
  target?.addEventListener('pagehide',leave);
  target?.addEventListener('pageshow',enter);
  function assertActive() { if(disposed || !active) throw new Error('페이지를 다시 열어 주세요.'); }
  function point(value) {
    if(!value || typeof value.name!=='string' || !value.name.trim() || !Number.isFinite(value.lat) || !Number.isFinite(value.lng) || Math.abs(value.lat)>90 || Math.abs(value.lng)>180) throw new Error('위치 형식을 확인해 주세요.');
    return {name:value.name,lat:value.lat,lng:value.lng};
  }
  return {
    setLocations({origin,destination}) {
      assertActive();
      const changes={};
      if(origin!==undefined) changes.origin=point(origin);
      if(destination!==undefined) changes.destination=point(destination);
      sequence++;pending?.abort();pending=null;
      state.request={...state.request,...changes};state.awaiting_route=true;
    },
    async send(text) {
      assertActive();
      if(typeof text!=='string' || !text.trim()) throw new Error('문장을 입력해 주세요.');
      const current=++sequence;pending?.abort();
      const controller=new AbortController();pending=controller;
      try {
        const response=await fetchImpl(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',
          signal:controller.signal,body:JSON.stringify({text,state:clone(state)})});
        if(current!==sequence || !active || disposed) return null;
        if(!response.ok) throw new Error('응답을 확인하지 못했습니다. 입력을 확인해 주세요.');
        const payload=await response.json();
        if(current!==sequence || !active || disposed) return null;
        state=clone(payload.state ?? {});
        const {state:privateState,...view}=payload;
        return view;
      } catch(error) {
        if(current!==sequence || controller.signal.aborted || !active || disposed) return null;
        throw error;
      } finally { if(current===sequence) pending=null; }
    },
    clear,
    dispose() {
      clear();disposed=true;active=false;
      target?.removeEventListener('pagehide',leave);target?.removeEventListener('pageshow',enter);
    }
  };
}
