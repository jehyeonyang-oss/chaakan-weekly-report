'use strict';
const $ = id => document.getElementById(id);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = x => typeof x === 'number' && Number.isFinite(x) ? x : null;
const n = x => num(x) === null ? '—' : Math.round(x).toLocaleString('ko-KR');
const won = x => num(x) === null ? '—' : n(x) + '원';
const percent = x => num(x) === null ? '—' : (x * 100).toLocaleString('ko-KR', {maximumFractionDigits:1}) + '%';
const ratio = (a,b) => num(a) !== null && num(b) !== null && b > 0 ? a/b : null;
const sum = (rows,key) => { const a = rows.map(r => typeof key === 'function' ? key(r) : r[key]).filter(x=>num(x)!==null); return a.length ? a.reduce((x,y)=>x+y,0) : null; };
const personKey = r => r.person_id || `${r.country}|${r.channel}|${r.id.toLowerCase()}`;
const uniq = rows => [...new Map(rows.map(r=>[personKey(r),r])).values()];
const safe = url => {try {const u=new URL(url);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
const link = (url,text) => safe(url) ? `<a href="${esc(safe(url))}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : esc(text||'—');
const addDays=(value,days)=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return null;const d=new Date(value+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);};
const stamp=x=>x?new Date(x).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}):'확인 전';
const ss = r => num(r.shares)!==null&&num(r.saves)!==null ? r.shares+r.saves : null;
const cost = r => r.source==='live'?num(r.content_cost):num(r.content_cost);
const confirmed = r => ['④','⑤','⑥','⑦','✅'].includes(r.stage);
const totalFee=rows=>rows.length&&rows.every(r=>r.free||num(r.price)!==null)?sum(rows,r=>r.free?0:r.price):null;
const due = r => addDays(r.upload,7);
const est = rows => rows.some(r=>r.views_est)?' <small class="est" title="샤오홍슈 조회수 미표시: 좋아요×75로 추정">추정</small>':'';
const mature = (r,t) => r.post_url && r.upload && due(r)<=t.asof && r.measured && r.measured>=due(r) && r.measured<=t.asof && num(r.views)!==null;
let payload=null, current=['content','marketing','overseas'].includes(location.hash.slice(1))?location.hash.slice(1):'content', windowKey='latest', details={},seq=0;
const STAGES=[['①','컨택','st1'],['④','협상 완료','st4'],['⑤','방문 일정 확정','st5'],['⑥','촬영 완료','st6'],['⑦','업로드 완료','st7'],['✅','완료','st8']];

function table(headers,body){return `<div class="tscroll"><table class="num"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;}
const td=(value,formatter=n)=>`<td${value==null?' class="na"':''}>${formatter(value)}</td>`;
function clickRow(cells,rows,renderer=peopleTable,extra=''){
  const key='detail-'+(++seq);details[key]={rows,renderer};
  return `<tr class="click ${extra}" data-detail="${key}" tabindex="0" role="button" aria-expanded="false"><td><span class="chev">▶</span>${cells[0]}</td>${cells.slice(1).map(c=>`<td>${c}</td>`).join('')}</tr>`;
}
function peopleTable(rows){
  if(!rows.length)return '<div class="empty">이 단계 인원이 없습니다.</div>';
  if(current!=='overseas')return table(['ID','담당','캠페인·라인','진행상황','계약금액','업로드일','게시물'],rows.map(r=>`<tr><td>${link(r.url,r.id)}</td><td>${esc(r.who)}</td><td>${esc(r.campaign)}</td><td>${esc(r.status)}</td><td>${r.free?'무상':esc(r.fee_label||won(r.price))}</td><td>${esc(r.upload||'—')}</td><td>${link(r.post_url,r.post_url?'게시물 ↗':'—')}</td></tr>`).join(''));
  return table(['ID','담당','국가 · 채널','진행상황','단가','평균 조회수','촬영일','매장','업로드'],rows.map(r=>`<tr><td>${link(r.url,r.id)}</td><td>${esc(r.who)}</td><td>${esc(r.country)} · ${esc(r.channel)}</td><td>${esc(r.status)}</td><td>${r.free?'무상':won(r.price)}</td>${td(r.avg)}<td>${esc(r.shoot||'—')}</td><td>${esc(r.store||'—')}</td><td>${link(r.post_url,r.upload||'—')}</td></tr>`).join(''));
}
function phase(rows){
  const p=rows.filter(confirmed);
  // One creator appears in only one stage; multiple deliverables stay at their earliest unfinished stage.
  const rank=['④','⑤','⑥','⑦','✅'];const best=new Map();
  p.forEach(r=>{const k=personKey(r),old=best.get(k);if(!old||rank.indexOf(r.stage)<rank.indexOf(old.stage))best.set(k,r);});
  // ① 컨택 is shown for overseas only and stays out of the confirmed total.
  const contact=rows.filter(r=>r.stage==='①'&&!best.has(personKey(r)));
  const buckets=STAGES.filter(([k])=>k!=='①'||current==='overseas').map(([k,label,color])=>({k,label:current!=='overseas'&&k==='⑤'?'제품 발송':current!=='overseas'&&k==='⑥'?'초안·검수':label,color,rows:k==='①'?contact:p.filter(r=>best.get(personKey(r)).stage===k)}));
  return `<div class="dsub">단계별</div><div class="stagebar">${buckets.filter(b=>b.rows.length&&b.k!=='①').map(b=>`<i class="${b.color}" style="width:${uniq(b.rows).length/Math.max(1,best.size)*100}%" title="${esc(b.label)} ${uniq(b.rows).length}명"></i>`).join('')}</div>`+
    table(['단계 (누르면 인원 목록)','인원','금액'],buckets.map(b=>clickRow([`<span class="dot ${b.color}"></span>${b.k} ${b.label}`,uniq(b.rows).length+'명',won(totalFee(b.rows))],b.rows)).join('')+clickRow(['합계',best.size+'명',won(totalFee(p))],p,peopleTable,'total'))+'<div class="fn">같은 인원은 중복 제외합니다.'+(current==='overseas'?' ① 컨택은 합계에 포함하지 않습니다.':'')+' 계약금액·배분액이 모두 확인된 경우에만 금액 합계를 표시합니다.</div>';
}
function observed(r){
  if(r.source!=='live')return r;
  const m=r.windows?.[windowKey]||{};
  return {...r,...Object.fromEntries(['views','likes','comments','shares','saves'].map(k=>[k,num(m[k])])),measured:m.at?new Date(m.at).toISOString().slice(0,10):null};
}
function weighted(rows,denominator,costFn){
  const eligible=rows.filter(r=>num(denominator(r))!==null&&num(costFn(r))!==null&&!r.free);
  return {value:ratio(sum(eligible,costFn),sum(eligible,denominator)),count:eligible.length};
}
function aggregateUploads(rows,t,overseas){
  const eligible=overseas?rows.filter(r=>mature(r,t)&&!r.free&&num(r.price)!==null):rows.map(observed).filter(r=>num(r.views)!==null&&!r.free);
  const priceFn=overseas?r=>r.price:cost;
  return {rows:eligible,count:eligible.length,price:sum(eligible,priceFn),views:sum(eligible,'views'),exp:sum(eligible,'exp_ss'),ss:sum(eligible,ss),cpv:weighted(eligible,r=>r.views,priceFn).value,expCost:weighted(eligible,r=>r.exp_ss,priceFn).value,ssCost:weighted(eligible,ss,priceFn).value};
}
function uploadDetail(rows,overseas,t){
  const values=overseas?rows:rows.map(observed);
  const headers=['ID','국가','담당','캠페인·라인','업로드','측정일','게시물',overseas?'단가':current==='marketing'?'비용 · 원본 기준':'콘텐츠비','조회수','좋아요 · 댓글','예상 공유·저장','공유+저장','결과 CPV','예상 공유·저장 단가','공유·저장 단가'];
  if(!overseas)headers.push('시딩 귀속매출','매출 집계기간');
  return table(headers,values.map(r=>{const ok=overseas?mature(r,t):true,c=overseas?r=>r.price:cost,p=r.free?null:c(r);return `<tr><td>${link(r.url,r.id)}</td><td>${esc(r.country)}</td><td>${esc(r.who)}</td><td>${esc(r.campaign)}</td><td>${esc(r.upload||'—')}</td><td>${esc(r.measured||'미수집')}</td><td>${link(r.post_url,'게시물 ↗')}</td><td>${r.free?'무상':won(p)}</td>${ok&&num(r.views)!==null?`<td>${n(r.views)}${est([r])}</td>`:td(null)}<td>${ok?`좋아요 ${n(r.likes)} · 댓글 ${n(r.comments)}`:'—'}</td>${td(r.exp_ss)}${td(ok?ss(r):null)}${td(ok?ratio(p,r.views):null,won)}${td(ratio(p,r.exp_ss),won)}${td(ok?ratio(p,ss(r)):null,won)}${!overseas?td(r.revenue,won)+`<td>${esc(r.revenue_window||'—')}</td>`:''}</tr>`;}).join(''));
}
function uploads(t,overseas){
  const rows=t.people.filter(r=>r.post_url&&r.upload&&r.stage!=='보류');
  const groups=overseas?['일본','대만·홍콩','샤오홍슈',...['한국','기타'].filter(g=>rows.some(r=>r.group===g))]:[...new Set(rows.map(r=>r.campaign||'미분류'))];
  const row=(label,rs,cls='')=>{const a=aggregateUploads(rs,t,overseas);const cells=overseas?[label,rs.length+'편',a.count+'편',won(a.price),n(a.views)+est(a.rows),n(a.exp),n(a.ss),won(a.cpv),won(a.expCost),won(a.ssCost)]:[label,rs.length+'편',a.count+'편',won(a.price),n(a.views),n(a.ss),won(a.ssCost),won(a.cpv),won(sum(rs,'revenue'))];return clickRow(cells,rs,r=>uploadDetail(r,overseas,t),cls);};
  const selector=!overseas?`<select id="window" aria-label="시딩 성과 측정 구간">${[['latest','최근 측정'],['48h','48시간'],['7d','7일'],['14d','14일']].map(([k,l])=>`<option value="${k}"${windowKey===k?' selected':''}>${l}</option>`).join('')}</select>`:'';
  return `<section class="box"><div class="toolbar"><h2>${overseas?'2. 업로드 인사이트':'크리에이터 시딩 성과'}</h2>${selector}</div><div class="h2sub">${overseas?'전체 · 국가별 줄을 누르면 게시물 세부내역이 펼쳐집니다. 합계는 업로드 7일 경과·조회수 확인·유상 게시물 기준입니다.':'캠페인·라인별 줄을 누르면 게시물별 성과가 펼쳐집니다. 선택한 측정 구간의 수치만 표시합니다.'}</div>`+
  (rows.length?table(overseas?['구분 (누르면 세부내역)','업로드','결과 산출','단가 합','조회수','예상 공유·저장','공유+저장','결과 CPV','예상 공유·저장 단가','공유·저장 단가']:['캠페인·라인 (누르면 세부내역)','업로드','수치 확인',current==='marketing'?'확인된 비용 · 원본 기준':'확인된 콘텐츠비','조회수','공유+저장','공유·저장 단가','CPV · 참고','시딩 귀속매출'],row('전체',rows,'total')+groups.map(g=>row(g,rows.filter(r=>(overseas?r.group:r.campaign||'미분류')===g))).join('')):'<div class="empty">아직 업로드된 게시물이 없습니다. 성과를 입력하면 이곳에 표시됩니다.</div>')+
  `<div class="fn">${overseas?'결과 CPV = 원고료 ÷ 조회수 · 공유·저장 단가 = 원고료 ÷ (공유 + 저장) · 무상은 비용 지표에서 제외합니다.':current==='marketing'?'브랜더진 비용 = 협업비 + 확인된 2차 활용비. 크리에이터 비용 = 관리시트의 귀속 월 건당 단가. 제품원가는 원본에 없어 포함하지 않습니다.':'콘텐츠비 = 원고료 + 제품원가. 비용·반응이 모두 확인된 게시물끼리 단가를 계산합니다. 시딩 귀속매출은 메타광고 매출과 합산하지 않습니다.'} 공유·저장 중 미확인 값이 있으면 단가를 계산하지 않습니다.</div></section>`;
}
function country(t){
  const p=t.people.filter(confirmed), groups=['일본','대만·홍콩','샤오홍슈',...['한국','기타'].filter(g=>p.some(r=>r.group===g)||num(t.targets[g])!==null)];
  const stat=rows=>({count:uniq(rows).length,expected:sum(uniq(rows),'avg'),result:sum(rows.filter(r=>mature(r,t)),'views')});
  const cards=groups.map(g=>{const a=stat(p.filter(r=>r.group===g)),goal=t.targets[g],scale=Math.max(goal||0,a.expected||0,a.result||0,1);return `<div class="ccard"><div class="t">${g} · ${a.count}명</div><div class="v">${n(a.expected)}</div><div class="s">예상 조회수 · 결과 ${n(a.result)}</div><div class="goal"><i class="e" style="width:${(a.expected||0)/scale*100}%"></i><i class="r" style="width:${(a.result||0)/scale*100}%"></i></div><div class="s">${goal?`목표 ${n(goal)} · 결과 ${percent(ratio(a.result,goal))}`:'목표 조회수 미정'}</div></div>`;}).join('');
  const row=(g,rs,goal,cls='')=>{const a=stat(rs);return `<tr class="${cls}"><td>${g}</td><td>${a.count}명</td>${td(goal)}${td(a.expected)}${a.result===null?td(null):`<td>${n(a.result)}${est(rs.filter(r=>mature(r,t)))}</td>`}${td(ratio(a.result,goal),percent)}</tr>`;};
  return `<div class="dsub">국가별 조회수</div><div class="cgrid">${cards}</div>`+table(['국가','인원','목표 조회수','예상 조회수','결과 조회수','목표 달성'],groups.map(g=>row(g,p.filter(r=>r.group===g),t.targets[g])).join('')+row('합계',p,sum(groups,g=>t.targets[g]),'total'))+'<div class="fn">예상 조회수 = 확정 인원의 평균 조회수 합 · 결과 조회수 = 업로드 7일 뒤 확인된 조회수 합</div>';
}
function seeding(t,overseas){
  let extra='';
  if(overseas)extra=country(t);
  else{const p=t.people.filter(confirmed),groups=[...new Set(p.map(r=>r.campaign||'미분류'))];extra='<div class="dsub">캠페인·라인별 진행</div>'+table(['캠페인·라인','확정 인원','업로드','확정 원고료'],groups.map(g=>{const rs=p.filter(r=>(r.campaign||'미분류')===g);return clickRow([esc(g),uniq(rs).length+'명',rs.filter(r=>r.post_url).length+'편',won(totalFee(rs))],rs);}).join('')||'<tr><td colspan="4" class="empty">아직 등록된 캠페인이 없습니다.</td></tr>');}
  return `<section class="box"><h2>${overseas?'1. 섭외 진행현황':'크리에이터 시딩 진행현황'}</h2><div class="h2sub">협상 완료부터 완료까지. 단계 줄을 누르면 인플루언서 목록이 펼쳐집니다.</div>${phase(t.people)}${extra}</section>`;
}
function adCost(r){if(num(r.total_cost)!==null)return r.total_cost;const keys=['spend','creator_cost','product_cost','production_cost'];return keys.every(k=>num(r[k])!==null)?keys.reduce((a,k)=>a+r[k],0):null;}
function adAgg(rows){return {spend:rows.every(r=>num(r.spend)!==null)?sum(rows,'spend'):null,revenue:rows.every(r=>num(r.revenue)!==null)?sum(rows,'revenue'):null,purchases:sum(rows,'purchases'),total:rows.length&&rows.every(r=>adCost(r)!==null)?sum(rows,adCost):null,impressions:sum(rows,'impressions'),clicks:sum(rows,'clicks'),ss:sum(rows,ss)};}
function ads(t,store=false){
  const rows=store?(t.store_ads||[]):t.ads.filter(r=>!r.date||r.date<=t.asof),a=adAgg(rows);
  const title=store?'매장 메타광고 · 별도 집계':'메타광고 성과';
  const body=rows.map(r=>`<tr><td>${link(r.url,r.campaign)}</td><td>${esc(r.channel||'메타')}</td><td>${esc(r.period||r.date||'—')}</td><td>${esc(r.status||r.objective||'—')}</td>${td(r.spend,won)}${td(adCost(r),won)}${td(r.impressions)}${td(r.clicks)}${td(ratio(r.clicks,r.impressions),percent)}${td(ss(r))}${td(ratio(r.spend,ss(r)),won)}${td(r.purchases)}${td(r.revenue,won)}${td(ratio(r.revenue,r.spend),percent)}${td(ratio(r.revenue,adCost(r)),percent)}</tr>`).join('');
  return `<section class="box"><h2>${title}</h2><div class="h2sub">${store?'매장 광고는 크리에이터 PA와 구분합니다. 매출·구매는 매장 POS에서 별도로 확인합니다.':current==='marketing'?'마케팅 허브의 파트너콘텐츠 광고 누적 실적입니다. 같은 소재의 광고를 합산하며, 구매·매출은 클릭 후 1일 귀속 기준입니다. 콘텐츠 비용의 광고별 배분이 없어 총비용 ROAS는 비워 둡니다.':'광고비와 콘텐츠비 포함 비용을 함께 확인합니다. 기존 운영 페이지의 누적값과 엑셀 일별 실적은 중복 입력하지 않습니다.'}</div>`+
  (rows.length?table(['크리에이터·캠페인','구분','기간','상태·목적','광고비','총비용','노출','클릭','CTR','공유+저장','광고 공유·저장당','구매','광고 귀속매출','광고비 ROAS','총비용 ROAS'],`<tr class="total"><td>합계</td><td>—</td><td>—</td><td>${rows.length}건</td>${td(a.spend,won)}${td(a.total,won)}${td(a.impressions)}${td(a.clicks)}${td(ratio(a.clicks,a.impressions),percent)}${td(a.ss)}${td(weighted(rows,ss,r=>r.spend).value,won)}${td(a.purchases)}${td(a.revenue,won)}${td(ratio(a.revenue,a.spend),percent)}${td(ratio(a.revenue,a.total),percent)}</tr>`+body):'<div class="empty">메타광고 성과가 아직 연결되지 않았습니다. 기존 운영 데이터가 연결되거나 팀 엑셀에 입력되면 표시됩니다.</div>')+
  '<div class="fn">총비용은 광고비와 확인된 콘텐츠 비용을 포함합니다. 비용 누락 시 총비용 ROAS는 산출하지 않습니다. 조회·클릭·공유·저장의 미확인은 0으로 처리하지 않습니다.</div></section>';
}
function render(){
  if(!payload)return;const t=payload.teams.find(x=>x.slug===current);if(!t)return;
  details={};seq=0;const overseas=current==='overseas';$('title').textContent=t.name;
  document.querySelectorAll('[data-team]').forEach(b=>{b.setAttribute('aria-selected',String(b.dataset.team===current));b.tabIndex=b.dataset.team===current?0:-1;});
  $('team-panel').setAttribute('aria-labelledby','tab-'+current);
  $('period').textContent=`${t.period?t.period+' · ':''}${t.asof} 기준 · 마지막 반영 ${stamp(payload.updated_at)}`;
  $('download').href=`templates/${encodeURIComponent(t.name+'_주간보고.xlsx')}`;
  $('source-link').hidden=!t.source_url;$('source-link').href=safe(t.source_url)||'#';
  const notice=t.source_state&&t.source_state!=='ok'?t.source_message:'';$('notice').textContent=notice||'';$('notice').hidden=!notice;
  const p=t.people.filter(confirmed),a=aggregateUploads(p.filter(r=>r.post_url),t,overseas),ad=adAgg(t.ads);
  const kpis=overseas?[[uniq(p).length+'명','섭외 확정','협상 완료 이상'],[won(totalFee(p)),'확정 금액','원고료 합'],[n(sum(uniq(p),'avg')),'예상 조회수','평균 조회수 합'],[n(sum(p.filter(r=>mature(r,t)),'views')),'결과 조회수','업로드 7일 이후 수치']]:current==='marketing'?[[won(ad.spend),'메타 광고비','원본 전체 기간 누적'],[won(ad.revenue),'광고 귀속매출','클릭 후 1일 귀속 기준'],[percent(ratio(ad.revenue,ad.spend)),'광고비 ROAS','광고 귀속매출 ÷ 광고비'],[uniq(p).length+'명','시딩 확정','같은 인물의 계정 중복 제외']]:[[uniq(p).length+'명','시딩 확정','협상 완료 이상'],[p.filter(r=>r.post_url).length+'편','시딩 업로드','게시물 링크 기준'],[won(a.ssCost),'공유·저장당 비용','확인된 콘텐츠비 기준'],[won(sum(p,'revenue')),'시딩 귀속매출','원본의 누적 귀속매출']];
  const unavailable=current==='marketing'&&t.source_state!=='ok'&&!t.people.length&&!t.ads.length;
  $('kpis').innerHTML=kpis.map(([v,l,s])=>`<div class="kpi"><b>${unavailable?'—':v}</b><span>${l}</span><em>${unavailable?'데이터 연결 대기':s}</em></div>`).join('');
  const talking=t.people.filter(r=>['②','③'].includes(r.stage));
  $('summary').innerHTML=`<li>섭외 확정 <strong>${uniq(p).length}명</strong> · 업로드 <strong>${p.filter(r=>r.post_url).length}편</strong> · 소통·협상 중 ${uniq(talking).length}명</li>`+(t.source_at?`<li>기존 운영 데이터 기준 <strong>${stamp(t.source_at)}</strong></li>`:'');
  if(unavailable)$('summary').innerHTML='<li>마케팅 허브 데이터를 불러오지 못했습니다. 연결 상태를 확인해 주세요.</li>';
  const seed=seeding(t,overseas)+uploads(t,overseas),meta=ads(t)+(t.store_ads?.length?ads(t,true):'');
  $('team-panel').innerHTML=overseas?seed:current==='marketing'?meta+seed:seed+meta;
  $('foot').textContent=`착한구두 · ${t.name} · 실제 확인된 수치만 집계 · 페이지는 1분마다 새 자료를 확인합니다.`;
  $('window')?.addEventListener('change',e=>{windowKey=e.target.value;render();});
}
async function refresh(){
  const button=$('refresh');button.disabled=true;
  try{const r=await fetch('data.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();if(!Array.isArray(d.teams)||d.teams.length!==3)throw Error();payload=d;render();
    const status=await fetch('status.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.json());if(status.state==='error'){$('notice').hidden=false;$('notice').textContent=status.message;}
  }catch{$('notice').hidden=false;$('notice').textContent='새 자료를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.';}finally{button.disabled=false;}
}
function switchTeam(slug){if(!['content','marketing','overseas'].includes(slug))return;current=slug;history.replaceState(null,'','#'+slug);render();}
document.querySelectorAll('[data-team]').forEach(b=>{b.addEventListener('click',()=>switchTeam(b.dataset.team));b.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const list=['content','marketing','overseas'],i=list.indexOf(current),next=list[(i+(e.key==='ArrowRight'?1:2))%3];switchTeam(next);$('tab-'+next).focus();});});
function toggle(row){const existing=row.nextElementSibling;if(existing?.classList.contains('sub')){existing.remove();row.setAttribute('aria-expanded','false');return;}const d=details[row.dataset.detail];if(!d)return;row.insertAdjacentHTML('afterend',`<tr class="sub"><td colspan="${row.children.length}"><div class="detail-wrap" style="width:${Math.max(240,row.closest('.tscroll').clientWidth-26)}px">${d.renderer(d.rows)}</div></td></tr>`);row.setAttribute('aria-expanded','true');}
document.addEventListener('click',e=>{const row=e.target.closest('tr[data-detail]');if(row&&!e.target.closest('a'))toggle(row);});
document.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)&&e.target.matches('tr[data-detail]')){e.preventDefault();toggle(e.target);}});
addEventListener('hashchange',()=>switchTeam(location.hash.slice(1)));
$('refresh').addEventListener('click',refresh);refresh();setInterval(refresh,60000);
window.ReportMath={sum,ss,ratio,adAgg,weighted,mature,aggregateUploads};
