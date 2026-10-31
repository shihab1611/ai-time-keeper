/* Company Workspace — separate from Time Keeper */
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function wtab(n){[0,1,2,3,4,5,6,7,8,9].forEach(i=>{document.getElementById('ws'+i).style.display=i===n?'':'none';document.getElementById('w'+i).className=i===n?'on':''});if(n===0&&typeof loadDash==='function')loadDash();if(n===1)loadEmp();if(n===2)loadAdv();if(n===3){if(typeof loadInvoice==='function')try{loadInvoice()}catch(e){};if(typeof igenLoad==='function')try{igenLoad()}catch(e){};if(typeof cinvLoad==='function')try{cinvLoad()}catch(e){};setTimeout(function(){const c=document.getElementById('addinvChat');if(c&&!c.dataset.started){c.dataset.started='1';if(typeof aiwWizardStart==='function')aiwWizardStart()}},300)};if(n===6||n===7){loadLabor();loadPhones()}if(n===8)loadProfit();if(n===9){try{wsBuildThemeGrid();wsPaintThemeGrid();wsApplySetLang();WUI.count()}catch(e){}}try{history.replaceState(null,'','#ws'+n)}catch(e){}}
function fmtSize(n){if(n==null)return '—';if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';if(n<1073741824)return (n/1048576).toFixed(1)+' MB';return (n/1073741824).toFixed(2)+' GB'}
let EMPS=[];
async function loadEmp(){
 const box=document.getElementById('empList');
 box.innerHTML='<div class="hint">লোড হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/employees');const j=await r.json();
  if(!j.ok)throw (j.error||'failed');
  EMPS=j.employees||[];
  document.getElementById('empCnt').textContent=EMPS.length+' জন';
  renderEmp();
 }catch(e){box.innerHTML='<div class="hint">❌ '+esc(e)+'</div>'}
}
function renderEmp(){
 const q=(document.getElementById('empSearch').value||'').toLowerCase();
 const list=EMPS.filter(e=>e.name.toLowerCase().includes(q));
 document.getElementById('empList').innerHTML=list.map(e=>{
  const init=esc(e.name.trim()[0]||'?');
  return `<div class="emp" onclick="openEmp('${esc(e.name).replace(/'/g,"\\'")}')"><div class="av">${init}</div><div><b>${esc(e.name)}</b><br><small>📄 ${e.files} ফাইল • ${fmtSize(e.size)}</small></div></div>`;
 }).join('')||'<div class="hint">কেউ নেই</div>';
}
async function openEmp(name){
 const d=document.getElementById('empDetail');
 d.style.display='';
 document.getElementById('empName').textContent='👤 '+name;
 const box=document.getElementById('empFiles');
 box.innerHTML='<div class="hint">লোড হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/employee-files?name='+encodeURIComponent(name));const j=await r.json();
  if(!j.ok)throw (j.error||'failed');
  box.innerHTML='<table><thead><tr><th>ফাইল</th><th>সাইজ</th><th></th></tr></thead><tbody>'+
   j.files.map(f=>`<tr><td>📄 ${esc(f.name)}</td><td>${fmtSize(f.size)}</td><td style="white-space:nowrap"><a class="file" target="_blank" href="/api/drive/download?view=1&path=${encodeURIComponent('separet all doc/'+name+'/'+f.name)}">👁️</a> <a class="file" href="/api/drive/download?path=${encodeURIComponent('separet all doc/'+name+'/'+f.name)}">⬇️</a></td></tr>`).join('')+
   '</tbody></table>';
  d.scrollIntoView({behavior:'smooth',block:'nearest'});
 }catch(e){box.innerHTML='<div class="hint">❌ '+esc(e)+'</div>'}
}
(function(){
 const go=()=>{const hm=(location.hash||'').match(/^#ws([0-8])$/);wtab(hm?+hm[1]:0)};
 if(document.readyState==='complete'||document.readyState==='interactive')setTimeout(go,50);
 else document.addEventListener('DOMContentLoaded',()=>setTimeout(go,50));
})();

/* ---- নিজস্ব ড্রপডাউন ------------------------------------------------------
   ব্রাউজারের নেটিভ select-এর অপশন কালার ঠিকমতো দেখা যায় না, তাই নিজের বানানো।
   আগে মেনু .xs-এর ভেতরেই বসত, কিন্তু .bigadd আর .card-এ overflow:hidden থাকায়
   মেনু কেটে যেত — ফলে ক্লিক করলে খুলতেই "হাইড" হয়ে যেত।
   এখন মেনু <body>-তে বসে position:fixed, তাই কোনো কাটিং-এ আটকায় না। --------- */
let XS_MENU=null, XS_SEL=null;
function xStyleOnce(){
 if(document.getElementById('xstyle'))return;
 const st=document.createElement('style');st.id='xstyle';
 st.textContent='.xs{position:relative}'
  +'.xsbtn{width:100%;display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.12);color:#f2f0ff;cursor:pointer;font-size:13px;text-align:left;font-family:inherit}'
  +'.xsbtn:hover{background:rgba(255,255,255,.22);border-color:#7dd3fc}'
  +'.xsbtn span:first-child{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:left}'
  +'.xsmenu{position:fixed;z-index:2147483000;display:none;min-width:190px;max-width:360px;max-height:46vh;overflow:auto;overscroll-behavior:contain;background:#12233a;border:1px solid rgba(255,255,255,.32);border-radius:12px;padding:6px;box-shadow:0 18px 50px rgba(0,0,0,.6)}'
  +'.xsmenu button{display:block;width:100%;text-align:left;padding:9px 12px;border:0;border-radius:9px;background:transparent;color:#f2f0ff;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
  +'.xsmenu button:hover,.xsmenu button.on{background:#7dd3fc;color:#082f49}';
 document.head.appendChild(st);
}
function xMenu(){
 if(!XS_MENU){XS_MENU=document.createElement('div');XS_MENU.className='xsmenu';document.body.appendChild(XS_MENU)}
 return XS_MENU;
}
function xHide(){
 if(XS_MENU)XS_MENU.style.display='none';
 XS_SEL=null;
}
function xPlace(menu,btn){
 if(!btn)return;
 const r=btn.getBoundingClientRect();
 const w=Math.max(Math.round(r.width),190);
 const h=menu.offsetHeight||240;
 let top=r.bottom+6;
 if(top+h>window.innerHeight-8)top=Math.max(8,Math.round(r.top)-h-6);   // নিচে জায়গা নেই → উপরে খুলবে
 let left=r.left;
 if(left+w>window.innerWidth-8)left=window.innerWidth-w-8;
 menu.style.minWidth=Math.min(w,360)+'px';
 menu.style.left=Math.max(8,Math.round(left))+'px';
 menu.style.top=top+'px';
}
function xSync(sel){
 const w=sel.closest('.xs');if(!w)return;
 const btn=w.querySelector('.xsbtn');if(!btn)return;
 const menu=xMenu();
 menu.innerHTML='';
 [...sel.options].forEach(o=>{
  const b=document.createElement('button');b.type='button';b.textContent=o.textContent;
  if(o.selected)b.className='on';
  b.onclick=ev=>{
   ev.stopPropagation();
   sel.value=o.value;
   const keep=XS_SEL;XS_SEL=null;
   try{
    if(typeof sel.onchange==='function')sel.onchange.call(sel);
    else sel.dispatchEvent(new Event('change',{bubbles:true}));
   }finally{XS_SEL=keep}
   xHide();
   const l=btn.querySelector('span');if(l)l.textContent=o.textContent;
  };
  menu.appendChild(b);
 });
 const l=btn.querySelector('span');const o=sel.options[sel.selectedIndex];
 if(l&&o)l.textContent=o.textContent;
 if(XS_SEL===sel&&XS_MENU.style.display!=='none')xPlace(menu,btn);
}
function xConvert(sel){
 if(sel._xdone)return;sel._xdone=1;xStyleOnce();
 const wrap=document.createElement('div');wrap.className='xs';
 const btn=document.createElement('button');btn.type='button';btn.className='xsbtn';
 const lbl=document.createElement('span');const chev=document.createElement('span');chev.textContent='▾';
 btn.appendChild(lbl);btn.appendChild(chev);
 sel.style.display='none';
 btn.onclick=ev=>{
  ev.stopPropagation();
  if(XS_SEL===sel){xHide();return}
  XS_SEL=sel;
  const menu=xMenu();
  menu.style.display='block';
  xSync(sel);
  xPlace(menu,btn);
 };
 sel.parentNode.insertBefore(wrap,sel);
 wrap.appendChild(btn);wrap.appendChild(sel);
 xSync(sel);
}
function xAll(root){
 xStyleOnce();
 (root||document).querySelectorAll('select').forEach(s=>{
  if(!s.closest('.xs'))xConvert(s);else xSync(s);
 });
}
/* বাইরে ক্লিক = বন্ধ, Esc = বন্ধ, স্ক্রল = ঠিক জায়গায় থাকবে */
document.addEventListener('click',e=>{
 if(!XS_MENU||XS_MENU.style.display==='none')return;
 if(XS_MENU.contains(e.target))return;
 if(e.target.closest&&e.target.closest('.xsbtn'))return;
 xHide();
},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape')xHide()});
addEventListener('scroll',()=>{
 if(!XS_SEL)return;
 const b=XS_SEL.closest('.xs')&&XS_SEL.closest('.xs').querySelector('.xsbtn');
 xPlace(xMenu(),b);
},true);
addEventListener('resize',xHide);

/* ---------------- WhatsApp ---------------- */
let PHONES={};
let WA_ADV={people:[],grand:0};
function waNum(raw){let s=String(raw||'').replace(/\D/g,'');if(s.indexOf('00')===0)s=s.slice(2);return s}
function waLink(num,text){
 const n=waNum(num);
 if(!n)return '';
 return 'https://wa.me/'+n+'?text='+encodeURIComponent(text||'');
}
function waOpen(num,text,label){
 const n=waNum(num);
 if(!n){alert('❌ '+label+' — ফোন নম্বর সেট করা নেই');return false}
 window.open(waLink(n,text),'_blank');
 return true;
}
function waSendByName2(btn){
 // লোকের কার্ডের <b> ট্যাগে নাম থাকে (নতুন লেআউট: পুরো কার্ড, পুরনো: পাশের ঘর)
 let n=null;
 const host=btn.closest('.labor')||btn.closest('.emp')||btn.parentElement;
 const b=host&&host.querySelector('b');
 if(b)n=b.textContent.trim();
 if(n)waSend(n,'account');
}
async function loadPhones(){
 try{
  const r=await fetch('/api/ws/phones');const j=await r.json();
  PHONES=j.phones||{};
  waSum();waRenderPhones();waFillSelects();
 }catch(e){}
}
function waKey(s){return String(s||'').toLowerCase().replace(/[^a-z]/g,'')}
function waPeople(){
 // লোকের তালিকা ও অ্যাডভাঞ্চের তালিকা এক করে — নাম হাত-লেখা বা কেস ভিন্ন হলেও একজনই
 const out=[],byKey={};
 const add=(name,extra)=>{
  const k=waKey(name);
  if(!k)return;
  if(byKey[k]){Object.assign(byKey[k],extra||{});return byKey[k]}
  const o=Object.assign({name:name,provider:'',w:null,adv:null},extra||{});
  byKey[k]=o;out.push(o);return o;
 };
 (LABOR.providers||[]).forEach(b=>b.workers.forEach(w=>add(w.name,{provider:b.provider,w:w})));
 (WA_ADV.people||[]).forEach(p=>add(p.name,{adv:p,provider:p.provider||''}));
 return out;
}
function waSum(){
 const n=waPeople().filter(x=>PHONES[x.name]).length;
 const el=document.getElementById('waSum');
 if(el)el.textContent=n+' নম্বর সেট / '+waPeople().length+' জন';
}
function waFillSelects(){
 const ppl=waPeople();
 const opt=(f)=>ppl.map(x=>'<option value="'+esc(x.name)+'">'+esc(x.name)+(x.provider?' ('+esc(x.provider)+')':'')+'</option>').join('');
 const a=document.getElementById('waAccPerson');if(a&&!a.options.length)a.innerHTML=opt();
 const t=document.getElementById('waMsgTo');
 if(t)t.innerHTML='<option value="">— কার কাছে —</option>'+opt();
 [['waBulkProv',''],['waDutyProv','— সব প্রোভাইডার —'],['waDayProv','— সব প্রোভাইডার —']].forEach(([id,first])=>{
  const s=document.getElementById(id);if(!s)return;
  const cur=s.value;
  s.innerHTML='<option value="">'+first+'</option>'+LABOR.providers.map(b=>'<option value="'+esc(b.provider)+'">'+esc(b.provider)+'</option>').join('');
  s.value=cur;
 });
 xAll(document.getElementById('ws7'));
}
function waRenderPhones(){
 const box=document.getElementById('waPhoneList');if(!box)return;
 const pv=document.getElementById('waBulkProv').value;
 const rows=waPeople().filter(x=>!pv||x.provider===pv);
 box.innerHTML=rows.map(x=>'<div class="wa-phone"><b style="min-width:190px">'+esc(x.name)+'</b>'
  +'<span class="pill prov">'+esc(x.provider||'—')+'</span>'
  +'<input id="ph_'+esc(x.name).replace(/\W/g,'')+'" value="'+esc(PHONES[x.name]||'')+'" placeholder="+971501234567">'
  +'<button class="ghost" style="margin:0;padding:4px 10px" onclick="waSavePhone(this)">💾</button>'
  +(PHONES[x.name]?'<button class="ghost" style="margin:0;padding:4px 10px" onclick="waSendByName(this)">💬</button>':'')
  +'</div>').join('');
 xAll(document.getElementById('waPhoneList'));
}
async function waSavePhone(btn){
 const inp=btn.parentElement.querySelector('input');
 const name=btn.parentElement.querySelector('b').textContent;
 const r=await fetch('/api/ws/phones',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({person:name,set:inp.value})});
 const j=await r.json();
 if(j.ok){await loadPhones();waRenderPhones();waFillSelects()}
}
function waSendByName(btn){
 const name=btn.parentElement.querySelector('b').textContent;
 waSend(name,'account');
}
function waBulkPaste(){
 const b=document.getElementById('waBulkBox');
 const open=b.style.display!=='none';
 b.style.display=open?'none':'';
 if(open)return;
 const rows=waPeople();
 b.innerHTML='<div class="hint">প্রতি লাইনে: <b>নাম,নম্বর</b> — উদাহরণ: <code>Nenu Miah, +971501234567</code></div>'
  +'<textarea id="waBulkTa" rows="8" style="width:100%;margin-top:6px;padding:10px;border-radius:10px;background:rgba(0,0,0,.3);color:var(--txt);border:1px solid rgba(255,255,255,.2);font-family:inherit">'
  +rows.map(x=>x.name+', '+(PHONES[x.name]?'+'+PHONES[x.name]:'')).join('\\n')+'</textarea>'
  +'<div style="margin-top:8px"><button class="ghost" onclick="waBulkSave()">💾 সব নম্বর সেভ করুন</button>'
  +'<span class="status" id="waBulkMsg"></span></div>';
}
async function waBulkSave(){
 const lines=(document.getElementById('waBulkTa').value||'').split('\\n');
 let ok=0,bad=[];
 for(const ln of lines){
  const i=ln.indexOf(',');
  if(i<0)continue;
  const nm=ln.slice(0,i).trim();
  const num=waNum(ln.slice(i+1));
  if(!nm||!num)continue;
  const r=await fetch('/api/ws/phones',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({person:nm,set:num})});
  const j=await r.json();
  if(j.ok){ok++}else{bad.push(nm)}
 }
 await loadPhones();
 const m=document.getElementById('waBulkMsg');
 if(m){m.className='status ok';m.textContent='✅ '+ok+' নম্বর সেভ হয়েছে'+(bad.length?', বাদ: '+bad.join(', '):'');}
}
/* ---- messages ---- */
function waAccText(name){
 const k=waKey(name);
 const l=waPeople().find(x=>waKey(x.name)===k)||{};
 const p=l.adv||(WA_ADV.people||[]).find(x=>waKey(x.name)===k);
 const L=[];
 L.push('Assalamu Alaikum '+l.name+'!,');
 if(p){
  L.push('');
  L.push('আপনার হিসাব (Advance):');
  L.push('মোট: '+p.total+' AED');
  L.push('Paid: '+p.paid+' AED');
  L.push('বাকি: '+p.balance+' AED');
 }
 if(l.provider)L.push('প্রোভাইডার: '+l.provider);
 if(l.w){
  L.push('ডিউটি: '+(l.w.off?'এখন বন্ধ':(l.w.site||'—')));
  if(l.w.start)L.push('শুরু: '+l.w.start);
  if(l.w.rate)L.push('রেট: '+l.w.rate+' AED/ঘণ্টা');
 }
 L.push('');
 L.push('ধন্যবাদ।');
 return L.join('\n');
}
function waDutyText(prov){
 const L=['📋 ডিউটি ও সাইট তালিকা — '+new Date().toLocaleDateString('en-GB'),''];
 LABOR.providers.filter(b=>!prov||b.provider===prov).forEach(b=>{
  L.push('👷 '+b.provider+'  (চলমান '+b.onDuty+' • বন্ধ '+b.off+')');
  b.workers.forEach(w=>L.push('   • '+w.name+' — '+(w.off?'এখন বন্ধ':(w.site||'সাইট লেখা নেই'))));
  L.push('');
 });
 return L.join('\\n');
}
function waDayText(prov){
 const L=['📅 আজকের ডিউটি রিমাইন্ডার — '+new Date().toLocaleDateString('en-GB'),''];
 LABOR.providers.filter(b=>!prov||b.provider===prov).forEach(b=>{
  const on=b.workers.filter(w=>!w.off);
  if(!on.length)return;
  L.push('👷 '+b.provider);
  on.forEach(w=>L.push('   • '+w.name+' — '+(w.site||'সাইট লেখা নেই')));
  L.push('');
 });
 L.push('সবাই সময়মতো সাইটে উপস্থিত থাকবেন।');
 return L.join('\\n');
}
function waAccPreview(){const n=document.getElementById('waAccPerson').value;document.getElementById('waAccPrev').textContent=n?waAccText(n):'— নাম বাছুন —'}
function waDutyPreview(){document.getElementById('waDutyPrev').textContent=waDutyText(document.getElementById('waDutyProv').value)}
function waSendBtn(name,kind){
 return '<button class="ghost" style="margin:2px" onclick="waSend(&quot;'+esc(String(name).replace(/"/g,'&quot;'))+'&quot;,&quot;'+kind+'&quot;)">💬 '+esc(name)+'</button>';
}
function waDayPreview(){
 const prov=document.getElementById('waDayProv').value;
 document.getElementById('waDayPrev').textContent=waDayText(prov);
 const box=document.getElementById('waDayList');
 const people=waPeople().filter(x=>!prov||x.provider===prov).filter(x=>x.w&&!x.w.off);
 box.innerHTML=people.length?('প্রত্যেককে আলাদা করে পাঠাতে: '+people.map(x=>waSendBtn(x.name,'day')).join(''))
  :'— কেউ নেই —';
}
function waSend(name,kind){
 const txt=kind==='account'?waAccText(name):waDayText('');
 const num=PHONES[name];
 const msg=document.getElementById('waMsg');
 const okOpen=waOpen(num,txt,name);
 if(msg){msg.textContent=okOpen?('✅ WhatsApp খুলেছে '+name+' — Send চাপুন'):('❌ '+name+' — নম্বর নেই');}
}
function waAccSend(){
 const n=document.getElementById('waAccPerson').value;
 if(!n){alert('❌ নাম বাছুন');return}
 const msg=document.getElementById('waMsg');
 const okOpen=waOpen(PHONES[n],waAccText(n),n);
 if(msg)msg.textContent=okOpen?('✅ WhatsApp খুলেছে — Send চাপুন'):('❌ '+n+' — নম্বর সেট করা নেই');
}
function waDutySend(){
 const prov=document.getElementById('waDutyProv').value;
 const targets=waPeople().filter(x=>!prov||x.provider===prov).filter(x=>PHONES[x.name]);
 if(!targets.length){alert('❌ কারো নম্বর নেই');return}
 if(!confirm(targets.length+' জনকে পাঠাবেন? প্রত্যেকের জন্য WhatsApp আলাদা ট্যাবে খুলবে — Send চাপতে হবে।'))return;
 targets.forEach((x,i)=>setTimeout(()=>window.open(waLink(PHONES[x.name],waDutyText(prov)),'_blank'),i*350));
 document.getElementById('waMsg').textContent='✅ '+targets.length+' টি WhatsApp ট্যাব খোলা হচ্ছে';
}
function waDaySend(){
 const prov=document.getElementById('waDayProv').value;
 const targets=waPeople().filter(x=>(!prov||x.provider===prov)&&x.w&&!x.w.off&&PHONES[x.name]);
 if(!targets.length){alert('❌ কারো নম্বর নেই');return}
 if(!confirm(targets.length+' জনকে ডিউটি রিমাইন্ডার পাঠাবেন?'))return;
 targets.forEach((x,i)=>setTimeout(()=>window.open(waLink(PHONES[x.name],waDayText(prov)),'_blank'),i*350));
 document.getElementById('waMsg').textContent='✅ '+targets.length+' টি WhatsApp ট্যাব খোলা হচ্ছে';
}
function waMsgSend(){
 const txt=document.getElementById('waMsgText').value.trim();
 const to=document.getElementById('waMsgTo').value;
 const msg=document.getElementById('waMsg');
 if(!txt){msg.textContent='❌ আগে বার্তা লিখুন';return}
 if(!to){msg.textContent='❌ কার কাছে পাঠাবেন বেছে নিন';return}
 const okOpen=waOpen(PHONES[to],txt,to);
 msg.textContent=okOpen?('✅ WhatsApp খুলেছে — Send চাপুন'):('❌ '+to+' — নম্বর সেট করা নেই');
}

/* ---------------- লোক ও সাইট (duty sheet) ---------------- */
let LABOR={providers:[]};
async function loadLabor(){
 const box=document.getElementById('labList');
 if(box)box.innerHTML='<div class="hint">লোড হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/labor');const j=await r.json();
  if(!j.ok)throw (j.error||'failed');
  LABOR={providers:j.providers||[]};
  fillProvSelect();
  if(box)renderLabor();
 }catch(e){if(box)box.innerHTML='<div class="hint">❌ '+esc(e)+'</div>'}
}
async function laborRefreshFromMaster(){
 const msg=document.getElementById('labMsg')||document.getElementById('labList');
 const old=msg.innerHTML;
 msg.innerHTML='<div class="hint">মাস্টার থেকে কপি হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/labor-refresh',{method:'POST'});
  const j=await r.json();
  if(!j.ok)throw j.error;
  await loadLabor();
  const m=document.getElementById('labMsg');
  if(m){m.className='status ok';m.textContent='✅ মাস্টার থেকে নতুন কপি নেওয়া হলো';}
 }catch(e){alert('❌ '+e);}
 }
function renderLaborRoster(){
 const box=document.getElementById('labRoster');
 if(!box)return;
 const P=LABOR.providers||[];
 const onDuty=P.reduce((t,b)=>t+(b.onDuty||0),0);
 const off=P.reduce((t,b)=>t+(b.off||0),0);
 const all=P.reduce((t,b)=>t+(b.workers||[]).length,0);
 const sites={};
 P.forEach(b=>(b.workers||[]).forEach(w=>{
  const st=(w.site||'').trim().toLowerCase();
  if(st&&!w.off&&['duty off','end','off','duty end'].indexOf(st)<0)sites[st]=1;
 }));
 const nSites=Object.keys(sites).length;
 const t=(c,i,k,v)=>'<div class="rost '+(c||'')+'"><span class="i">'+i+'</span>'
  +'<span class="t"><b>'+v+'</b><span>'+k+'</span></span></div>';
 const rows=P.map(b=>{
  const tot=(b.workers||[]).length||1;
  const w1=Math.round((b.onDuty||0)/tot*100),w2=100-w1;
  const meta='<b>'+(b.onDuty||0)+'</b> চলমান'
   +(b.off?'<b class="off">'+b.off+'</b> বন্ধ':' <span style="opacity:.55">সবাই চলমান</span>');
  return '<div class="rrow"><div class="nm">👷 '+esc(b.provider)+'</div>'
   +'<div class="rbar"><i style="width:'+w1+'%"></i>'
   +(b.off?'<i class="offpart" style="width:'+w2+'%"></i>':'')
   +'</div><div class="rmeta">'+meta+'</div></div>';
 }).join('');
 box.innerHTML='<div class="roster-top">'
  +t('','👷','প্রোভাইডার',P.length)
  +t('','👥','মোট জন',all)
  +t('on','🟢','চলমান',onDuty)
  +t('off','⏸','বন্ধ',off)
  +t('','📍','সাইট',nSites)
  +'</div>'
  +'<div class="roster-mid">প্রতিটি প্রোভাইডার — চলমান ও বন্ধ</div>'
  +'<div class="rlist">'+(rows||'<div class="rnone">কোনো প্রোভাইডার নেই</div>')+'</div>';
 try{if(typeof WUI!=='undefined'&&WUI&&WUI.count)WUI.count()}catch(e){}
}
function renderLabor(){
 renderLaborRoster();
 const se=document.getElementById('labSearch');
 const q=se?se.value.trim().toLowerCase():'';
 const groups=LABOR.providers
  .map(b=>({b:b,ws:b.workers.filter(w=>!q||[w.name,w.legal,w.site,b.provider].join(' ').toLowerCase().includes(q))}))
  .filter(g=>g.ws.length);
 document.getElementById('labList').innerHTML=groups.map(g=>{
 const b=g.b;
  return '<div class="pgroup labgrp" onclick="labToggleGrp(this)" title="তুলতে/খুলতে ক্লিক করুন"><span>👷 '+esc(b.provider)+'</span><span class="hint" style="font-weight:600">চলমান '+b.onDuty+' • বন্ধ '+b.off+' <b class="labcaret">▾</b></span></div>'
  +g.ws.map(w=>{
   const hD=(w.cmtDate||'');
   const hS=(w.cmtSite||'');
   const hist=(hD||hS)
    ?'<div class="labw-hist">'
     +(hD?'<div>💬 '+esc(hD)+'</div>':'')
     +(hS?'<div class="hist-site">📍 সাইট ঘর: '+esc(hS)+'</div>':'')
     +'</div>':'';
   const site=w.off?'<span class="chip off">⏸ এখন বন্ধ</span>'
    :(w.site?'<span class="chip site">📍 '+esc(w.site)+'</span>':'<span class="chip mute">📍 সাইট লেখা নেই</span>');
   return '<div class="labor labw'+(w.off?' offduty':'')+'" data-col="'+(w.col||0)+'" data-row="'+(w.row||0)+'">'
    +'<div class="labw-row">'
    +'<div class="labw-id"><b>'+esc(w.name)+'</b>'+(w.legal?'<small>📜 '+esc(w.legal)+'</small>':'')+'</div>'
    +'<div class="labw-chips">'+site
    +'<span class="chip'+(w.start?'':' mute')+'">'+(w.start?'🗓️ '+esc(w.start):'🗓️ তারিখ নেই')+'</span>'
    +(w.rate?'<span class="chip">💲 '+w.rate+'/ঘণ্টা</span>':'<span class="chip mute">💲 রেট নেই</span>')
    +'</div>'
    +'<div class="labw-acts">'
    +'<button class="ghost iact" title="এডিট / কমেন্ট" onclick="labEdit('+(w.col||0)+','+(w.row||0)+')">✏️</button>'
    +'<button class="ghost iact" title="WhatsApp পাঠান" onclick="waSendByName2(this)">💬</button>'
    +'<button class="ghost iact danger" title="মুছুন" onclick="labDel('+(w.col||0)+','+(w.row||0)+')">🗑️</button>'
    +'</div></div>'+hist+'</div>';
  }).join('');
 }).join('')||'<div class="hint">কিছু পাওয়া যায়নি</div>';
 xAll(document.getElementById('labList'));
}
function labToggleGrp(el){
 const hide=!el.classList.contains('collapsed');
 el.classList.toggle('collapsed',hide);
 let n=el.nextElementSibling;
 while(n&&!n.classList.contains('pgroup')){n.style.display=hide?'none':'';n=n.nextElementSibling}
}
async function labPost(body,okMsg){
 const box=document.getElementById('labMsg')||document.getElementById('labList');
 const old=box.innerHTML;
 box.innerHTML='<div class="hint">সেভ হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/labor-save',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify(body)});
  const j=await r.json();
  if(!j.ok)throw j.error;
  await loadLabor();
  const m=document.getElementById('labMsg');
  if(m){m.className='hint';m.style.color='#4ade80';m.textContent=(okMsg||'✅ সেভ হয়েছে');}
  return true;
 }catch(e){
  box.innerHTML=old;
  if(/এক্সেলে ফাইলটা খোলা/.test(String(e))){
   alert('⚠️ এক্সেলে ফাইলটা এখনো খোলা আছে।\n\nএক্সেল বন্ধ করে আবার চেষ্টা করুন —\nতাহলেই বট লিখতে পারবে।');
  }else{alert('❌ '+e)}
  return false;
 }
}
async function labDel(col,row){
 const blk=LABOR.providers.find(b=>(b.workers||[]).some(w=>w.col===col&&w.row===row));
 const w=blk?blk.workers.find(x=>x.col===col&&x.row===row):null;
 if(!w)return;
 if(!confirm('"'+w.name+'" মুছে যাবে? (ব্যাকআপ নেওয়া হবে)'))return;
 await labPost({act:'del',col:col,row:row},'✅ মুছে ফেলা হয়েছে: '+w.name);
}
async function labForm(col,row,mode){
 const blk=LABOR.providers.find(b=>(b.workers||[]).some(w=>w.col===col&&w.row===row));
 const w=blk?blk.workers.find(x=>x.col===col&&x.row===row):null;
 if(!w)return;
 const box=document.getElementById('lf'+col+'_'+row);
 if(box){
  box.style.display=box.style.display==='none'?'block':'none';
  return;
 }
  const h=(w.cmtDate||'');
  const hs=(w.cmtSite||'');
 const d=document.createElement('div');
 d.id='lf'+col+'_'+row;
 d.className='lform';
 d.innerHTML=
   '<div class="row"><div><label class="hint">নাম</label><input id="lfn_'+col+'_'+row+'" value="'+esc(w.name)+'"></div>'
  +'<div><label class="hint">ডিউটি শুরু</label><input id="lfs_'+col+'_'+row+'" placeholder="YYYY-MM-DD" value="'+esc(w.start||'')+'"></div>'
  +'<div><label class="hint">রেট</label><input id="lfr_'+col+'_'+row+'" placeholder="7" value="'+(w.rate==null?'':esc(String(w.rate)))+'"></div>'
  +'<div><label class="hint">সাইট</label><input id="lfp_'+col+'_'+row+'" placeholder="Al Maraj / END" value="'+esc(w.site||'')+'"></div></div>'
   +'<div style="margin-top:6px"><label class="hint">💬 কমেন্ট — <b>তারিখের ঘরে</b> বসবে (এক্সেলে লাল ত্রিভূজ)</label>'
  +'<textarea id="lfc_'+col+'_'+row+'" rows="3" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.12);color:var(--txt);font-family:inherit">'+esc(h)+'</textarea></div>'
   +'<div style="margin-top:6px"><label class="hint">💬 সাইটের ঘরের নোট — <b>সাইটের ঘরে</b> বসবে (খালি রাখলে মুছে যাবে)</label>'
   +'<textarea id="lfsn_'+col+'_'+row+'" rows="2" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08);color:var(--txt);font-family:inherit;opacity:.92">'+esc(hs)+'</textarea></div>'
  +'<div style="margin-top:8px"><button class="ghost" onclick="labSave('+col+','+row+')">💾 সেভ করুন</button>'
  +'<button class="ghost" onclick="document.getElementById(\'lf'+col+'_'+row+'\').remove()">বাতিল</button>'
  +'<span class="status" id="lfs2_'+col+'_'+row+'"></span></div>';
 const host=document.querySelector('#labList .labor[data-col="'+col+'"][data-row="'+row+'"]');
 if(host)host.after(d);
 else if(document.getElementById('labList'))document.getElementById('labList').appendChild(d);
}
async function labSave(col,row){
 const g=(p)=>document.getElementById(p+col+'_'+row);
 const msg=document.getElementById('lfs2'+col+'_'+row);
 const name=g('lfn_').value.trim();
 if(!name){msg.className='status';msg.textContent='❌ নাম লিখুন';return}
 const body={act:'edit',col:col,row:row,comment:g('lfc_').value,siteComment:g('lfsn_').value,
  values:{name:name,start:g('lfs_').value.trim(),rate:g('lfr_').value.trim(),site:g('lfp_').value.trim()}};
 const ok=await labPost(body,null);
 if(ok){msg.className='status ok';msg.textContent='✅ সেভ হয়েছে';setTimeout(()=>{const e=document.getElementById('lf'+col+'_'+row);if(e)e.remove();},900);}
}
async function labEdit(col,row){labForm(col,row,'edit')}
async function labComment(col,row){labForm(col,row,'comment')}
async function labAdd(){
 const box=document.getElementById('labAddBox');
 if(box.style.display==='none'||!box.style.display){box.style.display='';return}
 box.style.display='none';
}
function labAddRow(){
 const box=document.getElementById('labAddBox');
 if(box.style.display==='none'||!box.style.display){box.style.display='';return}
 const pv=document.getElementById('laProv').value;
 const nm2=document.getElementById('laName').value.trim();
 const st=document.getElementById('laStart').value.trim();
 const rt=document.getElementById('laRate').value.trim();
 const site=document.getElementById('laSite').value.trim();
 if(!nm2){alert('❌ লোকের নাম লিখুন');return}
 labPost({act:'add',provider:pv,name:nm2,start:st,rate:rt,site:site},
  '✅ যোগ হয়েছে: '+nm2).then(ok=>{if(ok){['laName','laStart','laRate','laSite'].forEach(i=>document.getElementById(i).value='')}});
}
function fillProvSelect(){
 const s=document.getElementById('naProv');
 if(!s)return;
 const cur=s.value;
 s.innerHTML='<option value="">— বেছে নিন —</option>'
  +LABOR.providers.map(b=>'<option value="'+esc(b.provider)+'">'+esc(b.provider)+' ('+b.workers.length+')</option>').join('')
  +'<option value="__none__">— প্রোভাইডার না (সরাসরি) —</option>';
 s.value=cur;
 naWorker();
 const la=document.getElementById('laProv');
 if(la&&la.innerHTML.indexOf('option')<0){
  la.innerHTML='<option value="">— নতুন প্রোভাইডার —</option>'
   +LABOR.providers.map(b=>'<option value="'+esc(b.provider)+'">'+esc(b.provider)+'</option>').join('');
 }
 xAll(document.getElementById('ws2'));
 xAll(document.getElementById('ws7'));
}
function naWorker(){
 const pv=document.getElementById('naProv').value;
 const w=document.getElementById('naWorker');
 if(!w)return;
 const done=()=>xAll(document.getElementById('ws2'));
 const list=(rows)=>w.innerHTML='<option value="">— লোক বাছুন —</option>'
  +rows.map(x=>'<option value="'+esc(x.name)+'">'+esc(x.name)+(x.off?' (বন্ধ)':'')+'</option>').join('');
 if(!pv){w.innerHTML='<option value="">— আগে প্রোভাইডার বাছুন —</option>';done();return}
 const people=waPeople();
 if(pv==='__none__'){
  const seen={},rows=[];
  people.forEach(x=>{const k=waKey(x.name);if(k&&!seen[k]){seen[k]=1;rows.push({name:x.name,off:!!(x.w&&x.w.off)})}});
  list(rows);done();return;
 }
 const b=LABOR.providers.find(x=>x.provider===pv);
 const seen={},rows=[];
 ((b&&b.workers)||[]).forEach(x=>{const k=waKey(x.name);if(k&&!seen[k]){seen[k]=1;rows.push({name:x.name,off:!!x.off})}});
 /* শুধু অ্যাডভাঞ্চ শিটে থাকা কিন্তু এই প্রোভাইডারের, তাদেরও নাম দেখাও */
 people.filter(x=>x.provider===pv).forEach(x=>{
  const k=waKey(x.name);
  if(k&&!seen[k]){seen[k]=1;rows.push({name:x.name,off:!!(x.w&&x.w.off)})}
 });
 list(rows);
 done();
}
async function advPickProv(pi){
 const p=(ADV.people||[])[pi];
 if(!p)return;
 const box=document.getElementById('ap'+pi);
 const opts=LABOR.providers.map(b=>`<option value="${esc(b.provider)}"${p.provider===b.provider?' selected':''}>${esc(b.provider)}</option>`).join('');
 box.innerHTML=`<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px">`
  +`<span class="hint">প্রোভাইডার:</span><select style="max-width:260px">${opts}</select>`
  +`<button class="ghost" style="margin:0" onclick="advSaveProv(${pi})">সেভ</button>`
  +`<button class="ghost" style="margin:0" onclick="document.getElementById('ap${pi}').innerHTML=''">বাতিল</button></div>`;
}
async function advSaveProv(pi){
 const p=(ADV.people||[])[pi];
 if(!p)return;
 const box=document.getElementById('ap'+pi);
 const sel=box.querySelector('select');
 if(!sel)return;
 try{
  const r=await fetch('/api/ws/labor-assign',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({person:p.name,provider:sel.value})});
  const j=await r.json();
  if(!j.ok)throw j.error;
  box.innerHTML='<span style="color:#4ade80">✅ প্রোভাইডার সেভ হয়েছে</span>';
  loadAdv();
 }catch(e){box.innerHTML='<span style="color:#fda4af">❌ '+esc(e)+'</span>'}
}

async function advNewAdd(){
 const msg=document.getElementById('naMsg');
 const prov=document.getElementById('naProv').value;
 const person=document.getElementById('naWorker').value.trim();
 const amt=document.getElementById('naAmt').value;
 const date=document.getElementById('naDate').value.trim();
 const reason=document.getElementById('naReason').value.trim();
 const paid=document.getElementById('naStatus').value==='paid';
 msg.className='status';msg.textContent='সেভ হচ্ছে…';
 if(!amt||!(+amt>0)){msg.textContent='❌ সঠিক টাকা লিখুন';return}
 if(!person){msg.textContent='❌ লোকের নাম বাছুন';return}
 try{
  const r=await fetch('/api/ws/advance-add',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({person:person,amount:+amt,date:date,paid:paid,reason:reason,
     provider:(prov&&prov!=='__none__')?prov:''})});
  const j=await r.json();
  if(!j.ok)throw j.error;
  msg.className='status ok';
  msg.textContent=(j.newPerson?'✅ নতুন লোক যোগ হয়েছে: ':'✅ অ্যাডভাঞ্চ যোগ হয়েছে: ')+person+' — '+amt+' AED';
  ['naAmt','naDate','naReason'].forEach(i=>document.getElementById(i).value='');
  loadLabor();
 }catch(e){msg.className='status';msg.textContent='❌ '+esc(e)}
}
let ADV={people:[],grand:0};
async function loadAdv(){
 const box=document.getElementById('advList');
 box.innerHTML='<div class="hint">লোড হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/advance');const j=await r.json();
  if(!j.ok)throw (j.error||'failed');
  ADV=j;WA_ADV=j;
  if(!LABOR.providers.length)await loadLabor();
  waSum();waFillSelects();renderAdv();
 }catch(e){box.innerHTML='<div class="hint">❌ '+esc(e)+'</div>'}
}
async function advImport(inp){
 if(!inp.files||!inp.files[0])return;
 const box=document.getElementById('advFilterInfo');
 const fd=new FormData();
 fd.append('file',inp.files[0]);
 fd.append('replace',document.getElementById('advImportReplace').checked?'1':'0');
 box.innerHTML='<div class="hint">⏳ ইমপোর্ট হচ্ছে…</div>';
 try{
  const r=await fetch('/api/ws/advance-import',{method:'POST',body:fd});
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  box.innerHTML='<div class="hint" style="color:#4ade80">✅ ইমপোর্ট হয়েছে: '+j.imported+' এন্ট্রি, '+j.people+' জন লোক</div>';
  inp.value='';
  loadAdv();
 }catch(e){box.innerHTML='<div class="hint" style="color:#fca5a5">❌ '+esc(e)+'</div>'}
}
function advExport(){location.href='/api/ws/advance-export';}
function advForm(i){
 const d=document.getElementById('af'+i);
 if(!d)return;
 d.style.display=d.style.display==='none'?'':'none';
}
async function advSave(i){
 const p=ADV.people[i];if(!p)return;
 const s=document.getElementById('af_s_'+i);
 const amt=document.getElementById('af_amt_'+i).value;
 let dt=document.getElementById('af_date_'+i).value.trim();
 if(!dt){const n=new Date();dt=String(n.getDate()).padStart(2,'0')+'/'+String(n.getMonth()+1).padStart(2,'0')+'/'+n.getFullYear()}
 const paid=document.getElementById('af_st_'+i).value==='paid';
 const reason=document.getElementById('af_rs_'+i).value.trim();
 s.className='status';s.textContent='সেভ হচ্ছে (ব্যাকআপসহ)…';
 try{const r=await fetch('/api/ws/advance-add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person:p.name,amount:amt,date:dt,paid,reason})});const j=await r.json();
 if(!j.ok)throw j.error;
 s.className='status ok';s.textContent='✅ যোগ হয়েছে (ব্যাকআপ: '+j.backup+')';loadAdv();
 }catch(e){s.className='status err';s.textContent='❌ '+e}
}
async function advDel(pi,ei,amt){
 const p=ADV.people[pi];if(!p)return;
 if(!confirm('"'+p.name+'" — '+amt+' AED এন্ট্রি মুছে যাবে? (ব্যাকআপ নেওয়া হবে)'))return;
 try{const r=await fetch('/api/ws/advance-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person:p.name,index:ei,amount:amt})});const j=await r.json();
 if(!j.ok)throw j.error;
 loadAdv();
 }catch(e){alert('❌ '+e)}
}
async function advPaid(pi,ei,amt){
 const p=ADV.people[pi];if(!p)return;
 if(!confirm('"'+p.name+'" — '+amt+' AED Paid (ক্লিয়ার) করবেন?'))return;
 try{const r=await fetch('/api/ws/advance-paid',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person:p.name,index:ei,amount:amt})});const j=await r.json();
 if(!j.ok)throw j.error;
 loadAdv();
 }catch(e){alert('❌ '+e)}
}
/* ---------- ফিল্টার: সব / পেইড / অনপেইড (ডিফল্ট অনপেইড) ---------- */
const ADV_FL={unpaid:{ico:'💰',bn:'অনপেইড (বাকি)'},paid:{ico:'✅',bn:'পেইড (ক্লিয়ার)'},all:{ico:'📋',bn:'সব এন্ট্রি'}};
let ADV_F='unpaid';
const advDone=e=>/paid|clear/i.test(e.status||'');
/* ---- "অনপেইড" সংখ্যাগুলো সুন্দর স্ট্যাট কার্ডে দেখানো ---- */
function aed(n){return Number(n||0).toLocaleString('en-US')}
function advStatStrip(cfg,people,entries,sum){
 const avg=entries?Math.round(sum/entries):0;
 const card=(cls,ico,k,v,u)=>'<div class="advStat '+cls+'">'
  +'<span class="ico">'+ico+'</span>'
  +'<span class="tx"><span class="k">'+k+'</span>'
  +'<span class="v">'+v+(u?'<span class="u">'+u+'</span>':'')+'</span></span></div>';
 return card('money','💰','মোট বাকি',aed(sum),'AED')
  +card('','👥','জন',aed(people),'জন')
  +card('','🧾','এন্ট্রি',aed(entries),'টি')
  +card('warn','📊',cfg.bn,entries?aed(avg):'—','AED গড়');
}
function advFilterToggle(){const m=document.getElementById('advFilterMenu');if(m)m.classList.toggle('open')}
function setAdvFilter(f){ADV_F=f;const m=document.getElementById('advFilterMenu');if(m)m.classList.remove('open');renderAdv()}
document.addEventListener('click',function(e){
 const m=document.getElementById('advFilterMenu');
 if(!m||!m.classList.contains('open'))return;
 if(m.contains(e.target)||(e.target.closest&&e.target.closest('#advFilterBtn')))return;
 m.classList.remove('open');
});

function renderAdv(){
 const q=(document.getElementById('advSearch').value||'').toLowerCase();
 const f=ADV_F;
 const met=(ADV.people||[]).filter(p=>p.name.toLowerCase().includes(q)).map(p=>{
  const all=p.entries||[];
  const shown=all.filter(e=>f==='all'||(f==='paid'?advDone(e):!advDone(e)));
  return {p:p,all:all,shown:shown};
 }).filter(x=>f==='all'||x.shown.length);
 document.getElementById('advGrand').textContent='মোট '+ADV.grand+' AED • '+ADV.people.length+' জন';
 const cfg=ADV_FL[f]||ADV_FL.unpaid;
 const fb=document.getElementById('advFilterBtn');
 if(fb)fb.textContent=cfg.ico+' '+cfg.bn+' ▾';
 document.querySelectorAll('#advFilterMenu button').forEach(b=>b.classList.toggle('on',b.dataset.f===f));
 const nEnt=met.reduce((s,x)=>s+x.shown.length,0);
 const sumAll=met.reduce((s,x)=>s+x.shown.reduce((t,e)=>t+(Number(e.amount)||0),0),0);
 const fi=document.getElementById('advFilterInfo');
 if(fi)fi.innerHTML=advStatStrip(cfg,met.length,nEnt,sumAll);
 document.getElementById('advList').innerHTML=met.map(x=>{
  const p=x.p, pi=ADV.people.indexOf(p);
  // ফাইলে হাতে লেখা "Total - xxx" পুরনো হিসাব, তাই আর দেখানো হচ্ছে না
  // — শুধু এন্ট্রি থেকে হিসাব করা Paid/বাকিই দেখানো হবে।
  const rows=x.shown.map(e=>{
   const ei=p.entries.indexOf(e);
   const done=advDone(e);
   const amt=Number(e.amount)||0;
   const paidBtn=done?'✓':`<button class="ghost" style="margin:0;padding:4px 10px" onclick="advPaid(${pi},${ei},${amt})">Paid করো</button>`;
   const delBtn=`<button class="ghost danger" style="margin:0;padding:4px 10px" onclick="advDel(${pi},${ei},${amt})">🗑️</button>`;
   const reason=e.reason||'';
    const rShort=reason.length>45?`<span class="rshort">${esc(reason.substring(0,45))}…</span><span class="rfull" style="display:none">${esc(reason)}</span> <button class="ghost rmore" style="margin:0;padding:1px 7px;font-size:11px;vertical-align:middle" onclick="advToggleReason(this)">▾ আরো</button>`:esc(reason);
    return `<tr><td>${amt}</td><td>${esc(e.date||'')}</td><td>${esc(e.status||'')}</td><td>${rShort}</td><td style="white-space:nowrap">${paidBtn} ${delBtn}</td></tr>`;
  }).join('');
  const shownSum=x.shown.reduce((t,e)=>t+(Number(e.amount)||0),0);
  const filt=f==='all'?'':` <small style="color:#7dd3fc">— দেখানো ${x.shown.length} টি / ${shownSum} AED</small>`;
  // কোন প্রোভাইডারের লোক, এখন কোথায় ডিউটিতে
  const prov=p.provider?`<span class="pill prov">👷 ${esc(p.provider)}</span>`:'';
  const site=p.dutyOff?'<span class="pill off">এখন বন্ধ</span>'
   :(p.site?`<span class="pill site">📍 ${esc(p.site)}</span>`:'');
  const dstart=p.dutyStart?`<span class="pill prov">🗓 ডিউটি শুরু ${esc(p.dutyStart)}</span>`:'';
  return `<div class="emp" style="cursor:default;align-items:flex-start"><div class="av">${esc(p.name.trim()[0]||'?')}</div><div style="flex:1"><b>${esc(p.name)}</b>${prov}${site}${dstart} — মোট <b>${p.total}</b> AED <small>(Paid ${p.paid} • বাকি ${p.balance})</small>${filt}`
   +`<button class="ghost" style="margin:0;padding:4px 10px" onclick="waSendByName2(this)">💬 WhatsApp</button>`
   +`<button class="ghost" style="margin:0;padding:4px 10px" onclick="advForm(${pi})">➕ Add</button>`
   +`<button class="ghost" style="margin:0;padding:4px 10px" onclick="advPickProv(${pi})">👷 প্রোভাইডার বদলান</button>`
   +`<div class="status" id="ap${pi}"></div>`
   +`<div id="af${pi}" style="display:none;margin-top:8px"><div class="row"><div><input id="af_amt_${pi}" type="number" min="1" placeholder="AED"></div><div><input id="af_date_${pi}" placeholder="তারিখ (খালি=আজ)"></div></div><div class="row" style="margin-top:6px"><div><select id="af_st_${pi}"><option value="paid">Paid (ক্লিয়ার)</option><option value="">বাকি</option></select></div><div><input id="af_rs_${pi}" placeholder="কারণ"></div></div><div style="margin-top:6px"><button class="ghost" onclick="advSave(${pi})">💾 সেভ</button></div><div class="status" id="af_s_${pi}"></div></div>`
   +`<table style="margin-top:6px"><thead><tr><th>AED</th><th>তারিখ</th><th>Status</th><th>কারণ</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
 }).join('')||'<div class="hint">এই ফিল্টারে কিছু নেই — অন্য সাইড বেছে নিন</div>';
}

// Show More/Less for long reason text
function advToggleReason(btn){
  const td=btn.closest('td');
  const s=td.querySelector('.rshort');
  const f=td.querySelector('.rfull');
  if(!s||!f)return;
  if(s.style.display==='none'){s.style.display='';f.style.display='none';btn.textContent='▾ আরো';}
  else{s.style.display='none';f.style.display='';btn.textContent='▴ কম';}
}

// ---- Invoice/Payment (extension: extensions/invoice.py) ----
async function loadInvoice(){
 try{
  const r=await fetch('/api/ws/invoice');const j=await r.json();
  if(!j.ok)throw j.error||'load failed';
  const st=document.getElementById('invStats');
  if(st)st.innerHTML=
   '<div class="advStat money"><div class="tx"><span class="k">📥 মোট ইন</span><span class="v">'+j.totalIn+' AED</span></div></div>'+
   '<div class="advStat warn"><div class="tx"><span class="k">📤 মোট আউট</span><span class="v">'+j.totalOut+' AED</span></div></div>'+
   '<div class="advStat"><div class="tx"><span class="k">📊 ব্যালান্স</span><span class="v">'+j.balance+' AED</span></div></div>';
  const list=document.getElementById('invList');
  if(!list)return;
  if(!j.entries.length){list.innerHTML='<div class="hint">এখনো কোনো এন্ট্রি নেই — উপর থেকে যোগ করুন।</div>';return;}
  list.innerHTML='<table><thead><tr><th>টাকা</th><th>তারিখ</th><th>দিক</th><th>বিবরণ</th><th></th></tr></thead><tbody>'+
   j.entries.map((e,i)=>{
    const dir=e.dir==='out'?'<span style="color:#fca5a5">📤 আউট</span>':'<span style="color:#86efac">📥 ইন</span>';
    return '<tr><td>'+esc(e.amount)+'</td><td>'+esc(e.date||'')+'</td><td>'+dir+'</td><td>'+esc(e.desc||'')+'</td><td style="white-space:nowrap"><button class="ghost danger" style="margin:0;padding:4px 10px" onclick="invDel('+i+')">🗑️</button></td></tr>';
   }).join('')+'</tbody></table>';
 }catch(e){const m=document.getElementById('invMsg');if(m){m.className='status err';m.textContent='❌ '+e}}
}
async function invAdd(){
 const amt=document.getElementById('inv_amt').value;
 const dt=document.getElementById('inv_date').value.trim();
 const dir=document.getElementById('inv_dir').value;
 const desc=document.getElementById('inv_desc').value.trim();
 const m=document.getElementById('invMsg');
 if(!amt||isNaN(parseFloat(amt))||parseFloat(amt)<=0){m.className='status err';m.textContent='⚠️ সঠিক টাকা লিখুন';return;}
 m.className='status';m.textContent='⏳ সেভ হচ্ছে...';
 try{
  const r=await fetch('/api/ws/invoice-add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount:amt,date:dt,dir:dir,desc:desc})});
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  m.className='status ok';m.textContent='✅ যোগ হয়েছে!';
  document.getElementById('inv_amt').value='';document.getElementById('inv_date').value='';document.getElementById('inv_desc').value='';
  loadInvoice();
 }catch(e){m.className='status err';m.textContent='❌ '+e}
}
async function invDel(i){
 if(!confirm('এই এন্ট্রি মুছে ফেলাবেন? (ব্যাকআপ নেওয়া হবে)'))return;
 const m=document.getElementById('invMsg');
 try{
  const r=await fetch('/api/ws/invoice-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i})});
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  loadInvoice();
 }catch(e){m.className='status err';m.textContent='❌ '+e}
}

// ---- Billing docs: Payment Statement + Company Invoice (extensions/) ----
let IGEN_PROVS=[], IGEN_BASE=null, IGEN_KIND='stmt';
let CINV_PROVS=[], CINV_BASE=null;

function amtWords(x){
 const ONES=['','ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE','TEN','ELEVEN','TWELVE','THIRTEEN','FOURTEEN','FIFTEEN','SIXTEEN','SEVENTEEN','EIGHTEEN','NINETEEN'];
 const TENS=['','','TWENTY','THIRTY','FORTY','FIFTY','SIXTY','SEVENTY','EIGHTY','NINETY'];
 function u1000(n){const o=[];if(n>=100){o.push(ONES[Math.floor(n/100)]+' HUNDRED');n%=100}if(n>=20){let t=TENS[Math.floor(n/10)];if(n%10)t+='-'+ONES[n%10];o.push(t)}else if(n>0)o.push(ONES[n]);return o.join(' ')}
 let n=Math.round(Number(x)||0);if(n===0)return 'ZERO';
 const p=[];for(const pair of [[1000000,'MILLION'],[1000,'THOUSAND']]){const d=pair[0],l=pair[1];if(n>=d){p.push(u1000(Math.floor(n/d))+' '+l);n%=d}}if(n)p.push(u1000(n));return p.join(' ');
}
const _fm=n=>Number(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});

// ================= PAYMENT STATEMENT =================
async function igenLoad(){
 try{
  const r=await fetch('/api/ws/invoice-gen-providers');const j=await r.json();
  if(!j.ok)throw j.error||'load failed';
  IGEN_PROVS=j.providers||[];
  const sel=document.getElementById('igen_prov');
  if(sel)sel.innerHTML=IGEN_PROVS.map(p=>'<option value="'+esc(p.key)+'">'+esc(p.display)+' ('+p.workers+' লোক)</option>').join('');
  // default month = data sheet's own month (September), not today
  const ms=document.getElementById('igen_month');
  if(ms)ms.value=String(j.data_month||new Date().getMonth()+1);
  // default PAY TO (editable) — settings-এর payto_client/payto_address
  const pt=document.getElementById('igen_payto');
  const pa=document.getElementById('igen_payaddr');
  if(pt)pt.value=(j.settings&&j.settings.payto_client)?j.settings.payto_client:(pt.value||'SHOMLUJ MIAH');
  if(pa)pa.value=(j.settings&&j.settings.payto_address)?j.settings.payto_address:(pa.value||'AJMAN, UAE');
 }catch(e){const m=document.getElementById('igenMsg');if(m){m.className='status err';m.textContent='❌ '+e}}
}
async function igenPreview(){
 const prov=(document.getElementById('igen_prov')||{}).value;
 const month=(document.getElementById('igen_month')||{}).value;
 const year=new Date().getFullYear();
 const m=document.getElementById('igenMsg');
 if(!prov){if(m){m.className='status err';m.textContent='⚠️ প্রোভাইডার সিলেক্ট করুন'}return;}
 if(m){m.className='status';m.textContent='⏳ পেমেন্ট স্টেটমেন্ট তৈরি হচ্ছে...'}
 try{
  const pt=(document.getElementById('igen_payto')||{}).value||'';
  const pa=(document.getElementById('igen_payaddr')||{}).value||'';
  const r=await fetch('/api/ws/invoice-gen?prov='+encodeURIComponent(prov)+'&month='+encodeURIComponent(month)
   +'&year='+encodeURIComponent(year)
   +'&client='+encodeURIComponent(pt)+'&address='+encodeURIComponent(pa));
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  IGEN_BASE=j;IGEN_KIND='stmt';
  igenRender();
  document.getElementById('igenPreviewWrap').style.display='';
  if(m){m.className='status ok';m.textContent='✅ প্রস্তুত — Unit Price / GAS / ADVANCE এডিট করুন, তারপর সেভ করুন'}
 }catch(e){if(m){m.className='status err';m.textContent='❌ '+e}}
}
function _peRow(w,i){
 return '<tr><td>'+w.sl+'</td><td class="l">'+esc(w.name)+'</td><td class="num">'+_fm(w.hours)+'</td>'+
 '<td class="num"><input class="peRate" data-i="'+i+'" type="number" step="0.25" value="'+Number(w.rate||0)+'"></td>'+
 '<td class="num amt">'+_fm(w.amount)+'</td><td class="num net">'+_fm(w.amount)+'</td></tr>';
}
let IGEN_PAPER='igenPaper';           // কোন বাক্সে প্রিভিউ দেখাবে
function igenRender(targetId){
 IGEN_PAPER=targetId||'igenPaper';
 const d=IGEN_BASE;if(!d)return;
 const rows=d.workers.map((w,i)=>_peRow(w,i)).join('');
 const isInv=(IGEN_KIND==='inv');
 const html=''+
 '<div class="inv-paper">'+
 '<div class="band">'+
   '<div class="mono">MM</div>'+
   '<div class="binfo"><div class="bco">'+esc(d.company.name)+'</div>'+
   '<div class="bct">PHONE: '+esc(d.company.contact)+'&nbsp;&nbsp;|&nbsp;&nbsp;EMAIL: '+esc(d.company.email)+'</div></div>'+
 '</div>'+
 '<div class="pbody">'+
 '<div class="ttl">'+(isInv?'COMPANY INVOICE':'PAYMENT STATEMENT')+'</div>'+
 '<div class="trule"></div>'+
 '<div class="meta"><span>'+(isInv?'INVOICE NO: ':'STATEMENT NO: ')+esc(d.invoice_no)+'</span><span>Date: '+esc(d.date)+'</span></div>'+
 '<div class="pf">'+
   '<div class="pl"><span class="lbl">'+(isInv?'BILL TO':'PAY TO')+'</span><div class="val">'+esc(d.client||'—')+(d.client?',':'')+'</div><div class="sub">'+esc(d.address||'')+'</div></div>'+
   '<div class="pr"><span class="lbl">FROM</span><div class="val">'+esc(d.from_name||'')+'</div></div>'+
 '</div>'+
 '<div><span class="pill">'+(isInv?'INVOICE':'PAYMENT')+' FOR THE MONTH OF '+esc(d.month_name)+' - '+d.year+'</span></div>'+
 '<table class="it"><thead><tr><th>SL No</th><th class="l">NAME</th><th>No. of Hours</th><th>Unit Price</th><th>Amount</th><th>'+(isInv?'Total Amount In AED':'Net Amount In AED')+'</th></tr></thead><tbody>'+rows+'</tbody></table>'+
 '<div class="sums">'+
 '<div class="row"><span>TOTAL</span><span><b id="peTotal">'+_fm(d.total)+'</b> AED</span></div>'+
 (isInv?'':
   '<div class="row"><span>GAS</span><span><input id="peGas" class="peAdj" type="number" step="0.5" value="'+Number(d.gas||0)+'"> AED</span></div>'+
   '<div class="row"><span>ADVANCE</span><span><input id="peAdv" class="peAdj" type="number" step="0.5" value="'+Number(d.advance||0)+'"> AED</span></div>')+
 '<div class="row net"><span>'+(isInv?'TOTAL PAYABLE AMOUNT':'NET PAYABLE AMOUNT')+'</span><span><b id="peNet">'+_fm(d.net)+'</b> AED</span></div>'+
 '</div>'+
 '<div class="wordsbox"><span class="wbar"></span>In words: (<span id="peWords">'+esc(d.in_words)+'</span> AED &amp; FIFTY-FILLS)</div>'+
 '<div class="footwrap">'+
   '<div class="thanks"><b>Thank You</b><div class="qnote">For queries contact: '+esc(d.company.email)+'</div></div>'+
   '<div class="sigbox"><div class="sigline"></div><div class="siglbl">Authorised Signatory</div></div>'+
 '</div>'+
 '</div>'+
 '<div class="fbar">'+esc(d.company.name)+'&nbsp;&nbsp;·&nbsp;&nbsp;'+(isInv?'COMPANY INVOICE':'PAYMENT STATEMENT')+'&nbsp;&nbsp;·&nbsp;&nbsp;Computer generated document</div>'+
 '</div>';
 const P=document.getElementById(IGEN_PAPER||'igenPaper');
 P.innerHTML=html;
 P.querySelectorAll('.peRate').forEach(inp=>inp.addEventListener('input',peRecalc));
 ['peGas','peAdv'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('input',peRecalc)});
}
function peRecalc(){
 const d=IGEN_BASE;if(!d)return;const isInv=(IGEN_KIND==='inv');
 const box=document.getElementById(IGEN_PAPER||'igenPaper');
 const q=id=>box?box.querySelector('#'+id):null;
 let total=0;
 (box?box.querySelectorAll('.peRate'):[]).forEach(inp=>{
  const i=+inp.dataset.i;const w=d.workers[i];
  const rate=Number(inp.value)||0;const amt=Math.round(w.hours*rate*100)/100;
  total+=amt;
  const tr=inp.closest('tr');const tds=tr.querySelectorAll('td');
  tds[4].textContent=_fm(amt);tds[5].textContent=_fm(amt);
 });
 total=Math.round(total*100)/100;
 let gas=0,adv=0;
 if(!isInv){
  gas=Number((q('peGas')||{}).value)||0;
  adv=Number((q('peAdv')||{}).value)||0;
 }
 const net=Math.round((total-gas-adv)*100)/100;
 const tEl=q('peTotal');if(tEl)tEl.textContent=_fm(total);
 const nEl=q('peNet');if(nEl)nEl.textContent=_fm(net);
 const wEl=q('peWords');if(wEl)wEl.textContent=amtWords(net);
}
function _peCollectRates(paperId){
 const rates={};
 const box=document.getElementById(paperId||IGEN_PAPER||'igenPaper');
 (box?box.querySelectorAll('.peRate'):[]).forEach(inp=>{
  const i=+inp.dataset.i;const w=IGEN_BASE.workers[i];
  rates[w.name]=Number(inp.value)||0;
 });
 return rates;
}
async function igenSave(){
 if(!IGEN_BASE){alert('আগে প্রিভিউ দেখুন');return;}
 const m=document.getElementById('igenMsg');
 const isInv=(IGEN_KIND==='inv');
 const curMonth = (IGEN_BASE && IGEN_BASE.month) || (document.getElementById('igen_month') || {}).value;
 const curYear = (IGEN_BASE && IGEN_BASE.year) || new Date().getFullYear();
 const body = {
    prov: IGEN_BASE.prov_key,
    month: parseInt(curMonth, 10),
    year: parseInt(curYear, 10),
    rates: _peCollectRates('igenPaper')
 };
 if(!isInv){
  const _ibox=document.getElementById('igenPaper');   // স্টেটমেন্টের নিজের প্রিভিউ বাক্স
  const _iq=id=>_ibox?_ibox.querySelector('#'+id):null;
  body.adv=Number((_iq('peAdv')||{}).value)||0;
  body.gas=Number((_iq('peGas')||{}).value)||0;
  body.client=(document.getElementById('igen_payto')||{}).value||'';
  body.address=(document.getElementById('igen_payaddr')||{}).value||'';
 }
 if(m){m.className='status';m.textContent='⏳ PDF সেভ হচ্ছে...'}
 try{
  const url=isInv?'/api/ws/company-invoice-save-one':'/api/ws/invoice-gen-save-one';
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  if(m){m.className='status ok';m.textContent='✅ সেভ হয়েছে → '+j.file+'   (নম্বর '+j.invoice_no+')'}
 }catch(e){if(m){m.className='status err';m.textContent='❌ '+e}}
}
function igenPrint(){
 const p=document.querySelector('#igenPaper .inv-paper');
 if(!p){alert('আগে প্রিভিউ দেখুন');return;}
 window.print();
}

// ================= COMPANY INVOICE =================
async function cinvLoad(){
 try{
  const r=await fetch('/api/ws/company-invoice-providers');const j=await r.json();
  if(!j.ok)throw j.error||'load failed';
  CINV_PROVS=j.providers||[];
  const sel=document.getElementById('cinv_prov');
  if(sel)sel.innerHTML=CINV_PROVS.map(p=>'<option value="'+esc(p.key)+'">'+esc(p.display)+' ('+p.workers+' লোক)</option>').join('');
  const ms=document.getElementById('cinv_month');
  if(ms)ms.value=String(j.data_month||new Date().getMonth()+1);
  cinvFillCfg();
 }catch(e){const m=document.getElementById('cinvMsg');if(m){m.className='status err';m.textContent='❌ '+e}}
}
function cinvFillCfg(){
 const prov=(document.getElementById('cinv_prov')||{}).value;
 const hit=CINV_PROVS.find(p=>p.key===prov);
 const cl=document.getElementById('cinv_client');
 const ad=document.getElementById('cinv_addr');
 const rt=document.getElementById('cinv_rate');
 if(cl)cl.value=hit?(hit.client||''):'';
 if(ad)ad.value=hit?(hit.address||''):'';
 if(rt)rt.value=hit?(hit.client_rate||''):'';
}
async function cinvCfgSave(){
 const prov=(document.getElementById('cinv_prov')||{}).value;
 if(!prov)return;
 const m=document.getElementById('cinvMsg');
 try{
  const r=await fetch('/api/ws/company-invoice-providers');const j=await r.json();
  const clients=j.clients||{};
  clients[prov]=clients[prov]||{};
  clients[prov].client=(document.getElementById('cinv_client')||{}).value||'';
  clients[prov].address=(document.getElementById('cinv_addr')||{}).value||'';
  clients[prov].client_rate=Number((document.getElementById('cinv_rate')||{}).value)||0;
  clients[prov].display=clients[prov].display||(CINV_PROVS.find(p=>p.key===prov)||{}).display||prov;
  const s=await fetch('/api/ws/company-invoice-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers:clients,company:j.company,settings:j.settings})});
  const sj=await s.json();
  if(!sj.ok)throw sj.error||'failed';
  const hit=CINV_PROVS.find(p=>p.key===prov);if(hit){hit.client=clients[prov].client;hit.address=clients[prov].address;hit.client_rate=clients[prov].client_rate;}
  if(m){m.className='status ok';m.textContent='✅ ক্লায়েন্ট কোম্পানি সেভ হয়েছে'}
 }catch(e){if(m){m.className='status err';m.textContent='❌ '+e}}
}
async function cinvPreview(){
 const prov=(document.getElementById('cinv_prov')||{}).value;
 const month=(document.getElementById('cinv_month')||{}).value;
 const m=document.getElementById('cinvMsg');
 if(!prov){if(m){m.className='status err';m.textContent='⚠️ সাইট সিলেক্ট করুন'}return;}
 if(m){m.className='status';m.textContent='⏳ কোম্পানি ইনভয়েস তৈরি হচ্ছে...'}
 try{
  const r=await fetch('/api/ws/company-invoice?prov='+encodeURIComponent(prov)+'&month='+encodeURIComponent(month));
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  CINV_BASE=j;IGEN_BASE=j;IGEN_KIND='inv';
  igenRender();
  document.getElementById('igenPreviewWrap').style.display='';
  document.getElementById('igenPaper').scrollIntoView({behavior:'smooth',block:'start'});
  if(m){m.className='status ok';m.textContent='✅ ইনভয়েস প্রস্তুত — Unit Price এডিট করে সেভ করুন'}
 }catch(e){if(m){m.className='status err';m.textContent='❌ '+e}}
}


// ================= ADD INVOICE =================
/* ডিফল্ট ইংরেজি — বাংলা শুধো ইউজার "বাং" চাপলে */
function AI_T(bn,en){
 try{ return (typeof WS_LANG!=='undefined' && WS_LANG==='bn') ? bn : (en===undefined?bn:en); }
 catch(e){ return bn; }
}
/* শুধো ইনভয়েস বাক্সটুকু প্রিন্ট — পুরো পেজ নয় */
function printOnly(containerId){
 const el=document.getElementById(containerId);
 if(!el||!el.querySelector('.inv-paper')){alert(AI_T('আগে প্রিভিউ দেখুন','See the preview first'));return;}
 el.classList.add('printTarget');
 document.body.classList.add('printingOnly');
 const done=()=>{
  document.body.classList.remove('printingOnly');
  el.classList.remove('printTarget');
  window.removeEventListener('afterprint',done);
 };
 window.addEventListener('afterprint',done);
 try{ window.print(); }catch(e){ done(); }
 setTimeout(done,2500);
}

// ---------- guided wizard ----------
let AIW = { step: 0, msgs: [] };
function aiwLog(role, text){
  AIW.msgs.push({role, text});
  const chat=document.getElementById('addinvChat');
  if(!chat) return;
  const d=document.createElement('div');
  d.style.cssText='margin:6px 0;display:flex;'+(role==='bot'?'justify-content:flex-start':'justify-content:flex-end');
  const b=document.createElement('div');
  b.style.cssText='max-width:85%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.4;'
    +(role==='bot'?'background:#1e3a5f;color:#e2e8f0':'background:#059669;color:#fff');
  b.textContent=text;
  d.appendChild(b);
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
}
function aiwClearStep(){ const s=document.getElementById('addinvStep'); if(s) s.innerHTML=''; }
function aiwField(html){ const s=document.getElementById('addinvStep'); if(s) s.innerHTML=html; }
function aiwNext(){ AIW.step++; aiwRenderStep(); }
function aiwWizardStart(){
  const chat=document.getElementById('addinvChat'); if(chat) chat.innerHTML='';
  AIW={step:0,msgs:[],data:{}};
  aiwLog('bot', AI_T('স্বাগতম! আমি আপনাকে ইনভয়েস বানাতে সাহায্য করব। প্রথম প্রশ্ন —','Welcome! I will help you build the invoice. First question —'));
  aiwRenderStep();
}
function aiwRenderStep(){
  aiwClearStep();
  const m=document.getElementById('addinvMsg');
  if(m){m.className='status';m.textContent='';}
  switch(AIW.step){
    case 0: // company name
      aiwLog('bot', AI_T('কোন কোম্পানি / সাইটের ইনভয়েস? (যেমন: SHOMLUJ MIAH)','Which company / site is this invoice for? (e.g. SHOMLUJ MIAH)'));
      aiwField('<div style="display:flex;gap:8px;flex-wrap:wrap"><input id="wiz_company" style="flex:1;min-width:180px" placeholder="'+AI_T('কোম্পানির নাম','Company name')+'" onkeydown="if(event.key===\'Enter\')aiwStep0Next()"><button class="ghost" onclick="aiwStep0Next()">'+AI_T('পরের ধাপ →','Next →')+'</button></div>');
      setTimeout(()=>{const e=document.getElementById('wiz_company');if(e)e.focus();},50);
      break;
    case 1: // address
      aiwLog('bot', AI_T('ঠিকানা? (খালি রাখলে এড়িয়ে যাবে)','Address? (leave blank to skip)'));
      aiwField('<div style="display:flex;gap:8px;flex-wrap:wrap"><input id="wiz_addr" style="flex:1;min-width:180px" placeholder="'+AI_T('যেমন: AJMAN, UAE','e.g. AJMAN, UAE')+'" onkeydown="if(event.key===\'Enter\')aiwStep1Next()"><button class="ghost" onclick="aiwStep1Next()">'+AI_T('পরের ধাপ →','Next →')+'</button></div>');
      setTimeout(()=>{const e=document.getElementById('wiz_addr');if(e)e.focus();},50);
      break;
    case 2: // month
      aiwLog('bot', AI_T('কোন মাসের ইনভয়েস?','Which month?'));
      addInvLoad(); // populate selects
      setTimeout(()=>{
        const ms=document.getElementById('addinv_month');
        if(!ms||!ms.options.length){ aiwField('<div class="hint">'+AI_T('মাস লোড হচ্ছে...','Loading months...')+'</div>'); setTimeout(aiwRenderStep,600); return; }
        let html='<div style="display:flex;flex-wrap:wrap;gap:6px">';
        for(const o of ms.options){
          html+='<button class="ghost" style="margin:0" onclick="document.getElementById(\'addinv_month\').value=\''+o.value+'\';aiwNext()">'+o.textContent+'</button>';
        }
        html+='</div>';
        aiwField(html);
      },400);
      break;
    case 3: // year
      aiwLog('bot', AI_T('কোন সাল?','Which year?'));
      setTimeout(()=>{
        const ys=document.getElementById('addinv_year');
        if(!ys||!ys.options.length){ aiwField('<div class="hint">'+AI_T('সাল লোড হচ্ছে...','Loading years...')+'</div>'); setTimeout(aiwRenderStep,600); return; }
        let html='<div style="display:flex;flex-wrap:wrap;gap:6px">';
        for(const o of ys.options){
          html+='<button class="ghost" style="margin:0" onclick="document.getElementById(\'addinv_year\').value=\''+o.value+'\';aiwNext()">'+o.textContent+'</button>';
        }
        html+='</div>';
        aiwField(html);
      },200);
      break;
    case 4: // load workers
      aiwLog('bot', AI_T('লোকদের ঘণ্টা পড়ছি...','Loading workers and hours...'));
      const ms=document.getElementById('addinv_month'); const ys=document.getElementById('addinv_year');
      // sync hidden client/addr from wizard state
      document.getElementById('addinv_client').value=AIW.data.company||'';
      document.getElementById('addinv_addr').value=AIW.data.addr||'';
      addInvLoad();
      setTimeout(()=>{
        const sel=document.getElementById('addinv_worker');
        if(!sel||!sel.options.length){ aiwField('<div class="hint">'+AI_T('কোনো ওয়ার্কার নেই','No workers found')+'</div>'); return; }
        let html='<div class="hint" style="margin-bottom:6px">'+AI_T('লোক সিলেক্ট করুন (একাধিক পারবেন):','Select workers (multiple allowed):')+'</div>';
        html+='<div style="display:flex;flex-direction:column;gap:4px;max-height:220px;overflow-y:auto;border:1px solid #1e3a5f;border-radius:8px;padding:6px">';
        for(const o of sel.options){
          html+='<label style="display:flex;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" class="wiz-wk" value="'+o.value+'" checked> '+o.textContent+'</label>';
        }
        html+='</div>';
        html+='<div style="margin-top:8px"><button class="ghost" onclick="aiwStep4Next()">'+AI_T('পরের ধাপ →','Next →')+'</button></div>';
        aiwField(html);
      },1200);
      break;
    case 5: // rate
      aiwLog('bot', AI_T('সিলেক্ট লোকের জন্য রেট (AED/hr) কত?','Rate (AED/hr) for selected workers?'));
      aiwField('<div style="display:flex;gap:8px;flex-wrap:wrap"><input id="wiz_rate" type="number" step="0.25" style="flex:1;min-width:120px" placeholder="'+AI_T('রেট','Rate')+'" onkeydown="if(event.key===\'Enter\')aiwStep5Next()"><button class="ghost" onclick="aiwStep5Next()">'+AI_T('প্রিভিউ বানাও →','Build preview →')+'</button></div>');
      setTimeout(()=>{const e=document.getElementById('wiz_rate');if(e)e.focus();},50);
      break;
    case 6: // preview
      aiwLog('bot', AI_T('ইনভয়েস তৈরি হচ্ছে...','Building invoice...'));
      // sync selected workers into hidden select
      const sel=document.getElementById('addinv_worker');
      if(sel){
        for(const o of sel.options){ o.selected=false; }
        (AIW.data.workers||[]).forEach(name=>{
          const o=[...sel.options].find(x=>x.value===name);
          if(o) o.selected=true;
        });
      }
      // apply rate
      const rate=AIW.data.rate||0;
      document.getElementById('addinv_rate').value=rate;
      addInvSetRate();
      // sync client/addr/month/year already set
      document.getElementById('addinv_client').value=AIW.data.company||'';
      document.getElementById('addinv_addr').value=AIW.data.addr||'';
      addInvPreview();
      aiwField('<div class="hint">'+AI_T('প্রিভিউ নিচে দেখুন। প্রতি লোকের Unit Price বদলাতে পারবেন। তারপর 💾 সেভ করুন।','See the preview below. Edit per-worker Unit Price if needed, then 💾 Save.')+'</div>');
      break;
    default:
      aiwField('<button class="ghost" onclick="aiwWizardStart()">'+AI_T('🔄 নতুন ইনভয়েস','🔄 New invoice')+'</button>');
  }
}
function aiwStep0Next(){
  const v=(document.getElementById('wiz_company')||{}).value||'';
  if(!v.trim()){ alert(AI_T('নাম দিন','Enter a name')); return; }
  AIW.data.company=v.trim();
  aiwLog('user', v.trim());
  document.getElementById('addinv_client').value=v.trim();
  aiwNext();
}
function aiwStep1Next(){
  const v=(document.getElementById('wiz_addr')||{}).value||'';
  AIW.data.addr=v.trim();
  aiwLog('user', v.trim()||AI_T('(খালি)','(blank)'));
  document.getElementById('addinv_addr').value=v.trim();
  aiwNext();
}
function aiwStep4Next(){
  const sel=document.querySelectorAll('.wiz-wk:checked');
  if(!sel.length){ alert(AI_T('কমপক্ষে একজন সিলেক্ট করুন','Select at least one')); return; }
  aiwLog('user', sel.length+' '+AI_T('জন সিলেক্ট','selected'));
    AIW.data.workers=[...sel].map(c=>c.value);
aiwNext();
}
function aiwStep5Next(){
  const v=(document.getElementById('wiz_rate')||{}).value||'';
  if(!v){ alert(AI_T('রেট দিন','Enter a rate')); return; }
  AIW.data.rate=Number(v)||0;
  aiwLog('user', v+' AED/hr');
  aiwNext();
}
function addInvWizardReset(){ aiwWizardStart(); }

async function addInvLoad(){
 try{
  const ms=document.getElementById('addinv_month');
  const ys=document.getElementById('addinv_year');
  const q=[];
  if(ms&&ms.value)q.push('month='+encodeURIComponent(ms.value));
  if(ys&&ys.value)q.push('year='+encodeURIComponent(ys.value));
  let u='/api/ws/add-invoice-providers';
  if(q.length)u+='?'+q.join('&');
  const r=await fetch(u);const j=await r.json();
  if(!j.ok)throw j.error||'load failed';
  if(ms){
   if(!ms.options.length){
    ms.innerHTML='';
    for(const [k,v] of Object.entries(j.month_names||{})){
     ms.innerHTML+='<option value="'+k+'">'+v+'</option>';
    }
   }
   if(!ms.value) ms.value=String(j.data_month||new Date().getMonth()+1);
  }
  if(ys){
   if(!ys.options.length){
    const base=parseInt(j.data_year,10)||new Date().getFullYear();
    let h='';
    for(let y=base+1;y>=base-2;y--)h+='<option value="'+y+'">'+y+'</option>';
    ys.innerHTML=h;
   }
   if(!ys.value && j.data_year) ys.value=String(j.data_year);
  }
  const sel=document.getElementById('addinv_worker');
  if(sel){
   const html=(j.workers||[]).map(function(w){
    const bn=(typeof WS_LANG!=='undefined'&&WS_LANG==='bn');
    const unit=bn?' \u0998\u09A3\u09CD\u099F\u09BE (\u09B0\u09C7\u099F ':' hrs (rate ';
    const txt=w.name+' \u2014 '+Number(w.hours||0)+unit+Number(w.rate||0)+')';
    return '<option value="'+esc(w.name)+'" data-hours="'+Number(w.hours||0)+'" data-rate="'+Number(w.rate||0)+'">'+esc(txt)+'</option>';
   }).join('');
   sel.innerHTML=html||('<option>'+AI_T('\u0995\u09CB\u09A8\u09CB \u0993\u09AF\u09BC\u09BE\u09B0\u09CD\u0995\u09BE\u09B0 \u09A8\u09C7\u0987','No workers found')+'</option>');
  }
 }catch(e){const m=document.getElementById('addinvMsg');if(m){m.className='status err';m.textContent='\u274C '+e}}
}
function addInvSetRate(){
 const sel=document.getElementById('addinv_worker');
 const rateInput=document.getElementById('addinv_rate');
 if(!sel||!rateInput)return;
 const rate=Number(rateInput.value)||0;
 const bn=(typeof WS_LANG!=='undefined'&&WS_LANG==='bn');
 const opts=sel.options;
 let n=0;
 for(let i=0;i<opts.length;i++){
  if(opts[i].selected){
   opts[i].dataset.rate=rate;
   n++;
  }
 }
 const m=document.getElementById('addinvMsg');
 if(m){m.className='status ok';m.textContent='\u2705 '+AI_T(n+'\u099C\u09A8 \u0993\u09AF\u09BC\u09BE\u09B0\u09CD\u0995\u09BE\u09B0\u09C7 \u09B0\u09C7\u099F \u09AC\u09B8\u09BE\u09A8\u09CB \u09B9\u09AF\u09BC\u09C7\u099B\u09C7: ','Rate set for '+n+' worker(s): ')+rate}
}
async function addInvPreview(){
 const client=document.getElementById('addinv_client')||{};
 const addr=document.getElementById('addinv_addr')||{};
 const monthSel=document.getElementById('addinv_month')||{};
 const yearSel=document.getElementById('addinv_year')||{};
 const sel=document.getElementById('addinv_worker')||{};
 const m=document.getElementById('addinvMsg');
 if(!client.value){if(m){m.className='status err';m.textContent='\u26A0\uFE0F '+AI_T('\u0995\u09CB\u09AE\u09AA\u09BE\u09A8\u09BF/\u09B8\u09BE\u0987\u099F\u09C7\u09B0 \u09A8\u09BE\u09AE \u09A6\u09BF\u09A8','Enter the company / site name')}return;}
 const opts=sel.options;
 const selectedNames=[];
 for(let i=0;i<opts.length;i++){ if(opts[i].selected) selectedNames.push(opts[i].value); }
 if(selectedNames.length===0){if(m){m.className='status err';m.textContent='\u26A0\uFE0F '+AI_T('\u0995\u09AE\u09AA\u0995\u09CD\u09B7\u09C7 \u098F\u0995\u099C\u09A8 \u0993\u09AF\u09BC\u09BE\u09B0\u09CD\u0995\u09BE\u09B0 \u09B8\u09BF\u09B2\u09C7\u0995\u09CD\u099F \u0995\u09B0\u09C1\u09A8','Select at least one worker')}return;}
 const month=monthSel.value||new Date().getMonth()+1;
 const year=parseInt(yearSel.value,10)||new Date().getFullYear();
 const rates={};
 for(let i=0;i<opts.length;i++){
  if(opts[i].selected) rates[opts[i].value]=Number(opts[i].dataset.rate||0);
 }
 // preview-box edits override
 const oldPaper=document.getElementById('addinvPaper');
 if(oldPaper){
  oldPaper.querySelectorAll('.peRate').forEach(inp=>{
   const i=+inp.dataset.i;
   // resolve worker name from ADDINV_BASE if available
  });
 }
 if(m){m.className='status';m.textContent='\u23F3 '+AI_T('\u0987\u09A8\u09AD\u09AF\u09BC\u09C7\u09B8 \u09A4\u09C8\u09B0\u09BF \u09B9\u099A\u09CD\u099B\u09C7...','Building invoice...')}
 try{
  const r=await fetch('/api/ws/add-invoice?client_key='+encodeURIComponent(client.value)
   +'&client_name='+encodeURIComponent(client.value)
   +'&client_address='+encodeURIComponent(addr.value||'')
   +'&month='+encodeURIComponent(month)
   +'&year='+encodeURIComponent(year)
   +'&rates='+encodeURIComponent(JSON.stringify(rates)));
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  ADDINV_BASE=j; IGEN_BASE=j; IGEN_KIND='inv';
  igenRender('addinvPaper');
  const wrap=document.getElementById('addinvPreviewWrap');
  if(wrap) wrap.style.display='';
  const paper=document.getElementById('addinvPaper');
  if(paper) paper.scrollIntoView({behavior:'smooth',block:'start'});
  if(m){
   if(j.warn){m.className='status err';m.textContent='\u26A0\uFE0F '+AI_T(j.warn,'Hours are empty for this month \u2014 check the selected month');}
   else{m.className='status ok';m.textContent='\u2705 '+AI_T('\u0987\u09A8\u09AD\u09AF\u09BC\u09C7\u09B8 \u09AA\u09CD\u09B0\u09B8\u09CD\u09A4\u09C1\u09A4 \u2014 \u09B2\u09CB\u0995\u09C7\u09B0 \u09B0\u09C7\u099F \u098F\u09A1\u09BF\u099F \u0995\u09B0\u09C7 \u09B8\u09C7\u09AD \u0995\u09B0\u09C1\u09A8','Invoice ready \u2014 edit per-worker rate, then save');}
  }
 }catch(e){if(m){m.className='status err';m.textContent='\u274C '+e}}
}
async function addInvSave(){
 if(!ADDINV_BASE){alert(AI_T('\u0986\u0997\u09C7 \u09AA\u09CD\u09B0\u09BF\u09AD\u09AF\u09BC\u09C7\u09C1 \u09A6\u09C7\u0996\u09C1\u09A8','See the preview first'));return;}
 const m=document.getElementById('addinvMsg');
 if(m){m.className='status';m.textContent='\u23F3 '+AI_T('PDF \u09B8\u09C7\u09AD \u09B9\u099A\u09CD\u099B\u09C7...','Saving PDF...')}
 try{
  let rates=_peCollectRates('addinvPaper');
  if(!Object.keys(rates).length){
   rates={};
   const sel=document.getElementById('addinv_worker');
   if(sel)for(let i=0;i<sel.options.length;i++){
    if(sel.options[i].selected) rates[sel.options[i].value]=Number(sel.options[i].dataset.rate||0);
   }
  }
  const body={
   client_key:ADDINV_BASE.client_key||'',
   client_name:ADDINV_BASE.client_name||'',
   client_address:ADDINV_BASE.client_address||'',
   month:ADDINV_BASE.month||new Date().getMonth()+1,
   year:ADDINV_BASE.year||new Date().getFullYear(),
   rates:rates
  };
  const r=await fetch('/api/ws/add-invoice-save-one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(!j.ok)throw j.error||'failed';
  if(m){m.className='status ok';m.textContent='\u2705 '+AI_T('\u09B8\u09C7\u09AD \u09B9\u09AF\u09BC\u09C7\u099B\u09C7 \u2192 ','Saved \u2192 ')+j.file+'   ('+AI_T('\u09A8\u09AE\u09CD\u09AC\u09B0 ','No. ')+j.invoice_no+')'}
 }catch(e){if(m){m.className='status err';m.textContent='\u274C '+e}}
}
function addInvPrint(){ printOnly('addinvPaper'); }
