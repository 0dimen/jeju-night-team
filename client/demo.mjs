import {createPageConversation} from './page_conversation.mjs';
const controller=createPageConversation();
const result=document.querySelector('#result'), input=document.querySelector('#text');
const locationStatus=document.querySelector('#location-status');
function node(tag,text,parent=result) {const el=document.createElement(tag);el.textContent=text;parent.append(el);return el;}
function clearView() {input.value='';locationStatus.textContent='선택한 위치 없음';result.replaceChildren();node('p','대화와 위치를 지웠습니다.');}
function show(view) {
  result.replaceChildren();node('p',view.message || '처리 결과');
  if(view.kind==='route') {
    const comparison=view.comparison_table;
    node('h2','경로 비교');node('p',comparison.value_meaning);
    const table=node('table',''),head=node('tr','',node('thead','',table));
    for(const label of ['경로','거리','예상 시간','CCTV 인접 비율']) node('th',label,head);
    const body=node('tbody','',table);
    for(const row of comparison.rows) {
      const tr=node('tr','',body);
      for(const value of [row.id,row.distance,row.duration,row.cctv_comparison_value==null?'자료 없음':row.cctv_comparison_value+'%']) node('td',String(value),tr);
    }
    node('p','비교 순위 1위: '+comparison.recommended_route_id);
    node('p',comparison.rank_reason);node('p',comparison.tradeoff);
    for(const limitation of comparison.limitations) node('p',limitation);
  } else if(view.kind==='report_preview') {
    node('p','제보 미리보기이며 저장·게시하지 않았습니다.');
    for(const question of view.questions || []) node('p',question.message || question.question || JSON.stringify(question));
  } else if(!view.message) node('pre',JSON.stringify(view,null,2));
}
document.querySelector('#locations').addEventListener('click',()=> {
  controller.setLocations({origin:{name:'SYNTHETIC 출발',lat:33.25,lng:126.56},destination:{name:'SYNTHETIC 도착',lat:33.25,lng:126.562}});
  result.replaceChildren();node('p','합성 위치를 선택했습니다. 출발 날짜와 시각을 알려 주세요.');
  locationStatus.textContent='합성 출발·도착 위치 선택됨';
});
document.querySelector('#reset').addEventListener('click',()=>{controller.clear();clearView();});
document.querySelector('#conversation').addEventListener('submit',async event=> {
  event.preventDefault();const text=input.value;input.value='';
  try {const view=await controller.send(text);if(view) {show(view);if(['emergency','reset','unsupported','data_question','report_preview'].includes(view.kind)) locationStatus.textContent='선택한 위치 없음';}}
  catch(error) {result.replaceChildren();node('p',error.message);}
});
window.addEventListener('pagehide',clearView);
window.addEventListener('pageshow',clearView);
