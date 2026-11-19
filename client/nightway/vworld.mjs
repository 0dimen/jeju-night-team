// VWorld 배경지도는 선택해서 불러온다. 브라우저에 인증키를 전달하지 않는다.
const NS='http://www.w3.org/2000/svg';
function node(tag,attrs={},text='') {const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);e.textContent=text;return e;}
export function worldPixel(point,z) {
  const size=256*2**z,lat=point[1]*Math.PI/180;
  return [(point[0]+180)/360*size,(1-Math.asinh(Math.tan(lat))/Math.PI)/2*size];
}
export async function drawVworld(view,host,isCurrent,signal) {
  const notice=document.createElement('p');host.replaceChildren(notice);notice.textContent='배경지도를 불러오는 중…';
  const response=await fetch('/maps/vworld/status',{cache:'no-store',signal});
  if(!response.ok)throw new Error('map status');
  const status=await response.json();
  if(!isCurrent())return;
  if(!status.configured)throw new Error('map key');
  const coordinates=view.routes.flatMap(r=>r.coordinates);
  let z=19, pixels;
  for(;z>=10;z--){pixels=coordinates.map(p=>worldPixel(p,z));if(Math.max(...pixels.map(p=>p[0]))-Math.min(...pixels.map(p=>p[0]))<=300 && Math.max(...pixels.map(p=>p[1]))-Math.min(...pixels.map(p=>p[1]))<=170)break;}
  const cx=(Math.min(...pixels.map(p=>p[0]))+Math.max(...pixels.map(p=>p[0])))/2;
  const cy=(Math.min(...pixels.map(p=>p[1]))+Math.max(...pixels.map(p=>p[1])))/2;
  const left=cx-190,top=cy-125;
  const svg=node('svg',{viewBox:'0 0 380 250',role:'img','aria-label':'VWorld 배경지도와 공개 경로·시설 위치',class:'route-map vworld-map'});
  const background=node('g'),facilities=node('g'),lines=node('g');svg.append(background,facilities,lines);
  host.append(svg);
  const project=p=>{const [x,y]=worldPixel(p,z);return [x-left,y-top];};
  for(const row of view.routes)lines.append(node('polyline',{points:row.coordinates.map(p=>project(p).join(',')).join(' '),stroke:row.id==='SHORTEST'?'#6c32c9':'#007b75',fill:'none','stroke-width':5,'stroke-dasharray':row.id==='SHORTEST'?'none':'7 6','data-route':row.id}));
  for(const [label,p] of [['출발',view.routes[0].coordinates[0]],['도착',view.routes[0].coordinates.at(-1)]]){
    const [x,y]=project(p);lines.append(node('circle',{cx:x,cy:y,r:6,fill:'#fff',stroke:'#222','stroke-width':2}));lines.append(node('text',{x:x+8,y:y-8,fill:'#111','font-size':13,stroke:'#fff','paint-order':'stroke','stroke-width':3},label));
  }
  const attribution=document.createElement('a');attribution.href='https://www.vworld.kr/';attribution.target='_blank';attribution.rel='noopener noreferrer';attribution.textContent='배경지도: 공간정보 오픈플랫폼 VWorld · 국토교통부';host.append(attribution);
  const legend=document.createElement('p');legend.textContent=(view.provider==='tmap'?'보라 실선: 받은 후보 중 짧은 길 · 청록 점선: 다른 보행 옵션':'보라 실선: 최단 · 청록 점선: 시설 우선')+' · 주황 점: CCTV · 파란 점: 조명. 시설 위치는 촬영·밝기·작동 범위를 뜻하지 않습니다.';host.append(legend);
  const tiles=[];
  for(let x=Math.floor(left/256);x<=Math.floor((left+380)/256);x++)for(let y=Math.floor(top/256);y<=Math.floor((top+250)/256);y++)tiles.push({x,y});
  let failures=0;
  async function tile({x,y}) {
    if(!isCurrent())return;
    let blobUrl;
    if(view.private_request){
      try {
        const r=await fetch('/maps/vworld/tile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({z,x,y}),cache:'no-store',signal});
        if(!r.ok)throw new Error('tile');
        const blob=await r.blob();if(!isCurrent())return;
        blobUrl=URL.createObjectURL(blob);
      }catch{failures++;return;}
    }
    if(!isCurrent()){if(blobUrl)URL.revokeObjectURL(blobUrl);return;}
    await new Promise(resolve=>{
      const image=node('image',{x:x*256-left,y:y*256-top,width:256,height:256});
      const done=()=>{signal?.removeEventListener('abort',done);if(blobUrl)URL.revokeObjectURL(blobUrl);resolve();};
      signal?.addEventListener('abort',done,{once:true});
      image.addEventListener('load',done,{once:true});image.addEventListener('error',()=>{failures++;done();},{once:true});
      background.append(image);image.setAttribute('href',blobUrl || `/maps/vworld/tiles/${z}/${x}/${y}.png`);
    });
  }
  // 브라우저·서버 양쪽에서 동시 요청 수를 제한한다.
  for(let i=0;i<tiles.length;i+=2)await Promise.all(tiles.slice(i,i+2).map(tile));
  if(!isCurrent())return;
  notice.textContent=failures?'배경지도 일부를 불러오지 못했습니다. 아래 좌표 도식과 계산 수치는 유지됩니다.':'VWorld 배경지도 연결 완료. 현장 보행 검토는 별도입니다.';
  const settings={route_provider:view.provider==='tmap'?'tmap':'osm',region:view.region,cctv_source:view.sources.cctv.name.includes('mois')?'standard':'datahub',preference:view.preference,light_radius:view.parameters.light_radius_m,cctv_radius:view.parameters.cctv_radius_m,weight:view.parameters.requested_weight,max_detour:view.parameters.max_detour};
  try {
    const r=view.map_points ? null : await fetch('/research/maps/facilities',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings),cache:'no-store',signal});
    if(r && !r.ok)throw new Error('facility');const data=view.map_points || await r.json();if(!isCurrent())return;
    for(const p of data.points){const [x,y]=project(p.coordinates);if(x<0||x>380||y<0||y>250)continue;const dot=node('circle',{cx:x,cy:y,r:3,fill:p.kind==='cctv'?'#d75d00':'#006bba',stroke:'#fff','stroke-width':1});dot.append(node('title',{},p.kind==='cctv'?'공개 CCTV 목록 위치':'공개 조명 목록 위치'));facilities.append(dot);}
    legend.textContent+=' '+data.notice+(data.truncated?' 표시 개수 제한이 적용되었습니다.':'');
  }catch{legend.textContent+=' 시설 위치 표시는 불러오지 못했습니다. 경로 지표는 유지됩니다.';}
}
