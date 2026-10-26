// Language helper for dash.js
function dashIsEn() {
    try {
        if (typeof WS_LANG !== 'undefined') return WS_LANG === 'en';
        return (localStorage.getItem('atk_lang') === 'en' || localStorage.getItem('ws_lang') === 'en');
    } catch(e) { return false; }
}

/* Entry dashboard: clock + profit/loss hero + tiles + dues (read-only) */
function dashTick() {
    try {
        const t = document.getElementById('dashClock');
        const d = document.getElementById('dashDate');
        if (!t || !d) return;
        const now = new Date();
        t.textContent = now.toLocaleTimeString('en-GB', {timeZone: 'Asia/Dubai', hour12: false});
        d.textContent = now.toLocaleDateString('en-GB', {timeZone: 'Asia/Dubai', weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'}) + ' • Dubai';
    } catch (e) {}
}
setInterval(dashTick, 1000);
document.addEventListener('DOMContentLoaded', dashTick);

function dashMonthMinus(ym, n) {
    const p = String(ym || '').split('-');
    const d = new Date(+p[0], (+p[1] || 1) - 1 - n, 1);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}
function dashCurMonth() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}
function pfBillMonthsDash() {
    const out = [];
    let m = '2026-09';
    const cur = dashCurMonth();
    while (m <= cur) {
        out.push(m);
        const q = m.split('-');
        const d = new Date(+q[0], (+q[1]) - 1 + 1, 1);
        m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }
    return out;
}

async function loadDash() {
    dashTick();
    const hero = document.getElementById('dashHero');
    const tiles = document.getElementById('dashTiles');
    const dues = document.getElementById('dashDues');
    try {
        // cycLoad() paints the cycle strip and returns nothing — it must never
        // be destructured. These are the three payloads the dashboard needs.
        const [pj, aj, lj] = await Promise.all([
            fetch('/api/ws/profit').then(r => r.json()),
            fetch('/api/ws/advance').then(r => r.json()),
            fetch('/api/ws/labor').then(r => r.json())
        ]);
        try { await cycLoad(); } catch (e) { /* the strip is optional */ }
        if (!pj.ok) throw new Error(pj.error || 'প্রফিট লোড হয়নি');
        const rates = pj.rates || {}, pay = pj.pay || {}, W = pj.workers || [];
        // per-worker site rates (site pays different rate per worker)
        let inc = 0, totH = 0, cost = 0, ratedH = 0;
        W.forEach(w => {
            const h = (+w.hours || 0);
            totH += h; cost += (+w.total || 0);
            if (w.srate != null) { inc += h * (+w.srate); ratedH += h; }
        });
        const month = dashCurMonth();
        const exTot = (pj.expenses || []).filter(e => (e.month || '') === month).reduce((s, e) => s + (+e.amount || 0), 0);
        const profit = Math.round((inc - cost - exTot) * 100) / 100;
        const fname = (pj.file || '').split('/').pop() || '—';
        const n2 = (x) => { x = Math.round((+x || 0) * 100) / 100; return (x % 1 === 0) ? x : x.toFixed(2); };

        const en = dashIsEn();
        const lblCompany = en ? '📊 Company Status' : '📊 কোম্পানির অবস্থা';
        const lblNoHours = en ? 'No hours recorded in Total T file' : 'Total T ফাইলে ঘণ্টা নেই';
        const lblSetRate = en ? (n2(totH) + ' hours logged, but site rate missing — <a class="file" href="javascript:wtab(8)">Set site rate in Profit tab</a>')
                              : (n2(totH) + ' ঘণ্টা আছে, কিন্তু সাইট রেট বসানো নেই — <a class="file" href="javascript:wtab(8)">প্রফিট ট্যাবে রেট বসান</a>');
        const lblProfit = en ? '📈 Profit ' : '📈 প্রফিট ';
        const lblLoss = en ? '📉 Loss ' : '📉 লস ';
        const lblSummary = en ? ('Income ' + n2(inc) + ' − Cost ' + n2(cost) + ' − Other ' + n2(exTot) + ' • <a class="file" href="javascript:wtab(8)">Details</a>')
                              : ('ইনকাম ' + n2(inc) + ' − খরচ ' + n2(cost) + ' − অন্যান্য ' + n2(exTot) + ' • <a class="file" href="javascript:wtab(8)">বিস্তারিত</a>');

        if (!totH) {
            hero.className = 'hero';
            hero.innerHTML = '<div class="k">' + lblCompany + '</div><div class="big">—</div><div class="sub2">' + lblNoHours + '</div>';
        } else if (!ratedH) {
            hero.className = 'hero';
            hero.innerHTML = '<div class="k">' + lblCompany + ' • ' + esc(fname) + '</div><div class="big">❓</div>' +
                '<div class="sub2">' + lblSetRate + '</div>';
        } else {
            const good = profit >= 0;
            hero.className = 'hero ' + (good ? 'profit' : 'loss');
            hero.innerHTML = '<div class="k">' + lblCompany + ' • ' + esc(fname) + '</div>' +
                '<div class="big">' + (good ? lblProfit : lblLoss) + n2(Math.abs(profit)) + ' AED</div>' +
                '<div class="sub2">' + lblSummary + '</div>';
        }

        const workers = (lj.providers || []).reduce((s, b) => s + b.workers.length, 0);
        const provs = (lj.providers || []).length;
        const tile = (ic, v, l, go) =>
            '<button class="tile" onclick="wtab(' + go + ')"><span class="ic">' + ic + '</span>' +
            '<span><span class="v">' + v + '</span><br><span class="l">' + l + '</span></span></button>';
        tiles.innerHTML =
            tile('👷', workers, en ? 'Workers' : 'জন লোক', 6) +
            tile('🏭', provs, en ? 'Providers' : 'প্রোভাইডার', 6) +
            tile('💰', n2((aj && aj.grand) || 0) + ' AED', en ? 'Total Advance' : 'এডভান্স মোট', 2) +
            tile('🧾', n2(exTot) + ' AED', en ? 'Monthly Expense' : 'এই মাসের খরচ', 8);

        // dues: this month + previous bill month (আয় M+1 এর ১৫, ব্যয় M+2 এর ১৫)
        const addM = (m, n) => { const p = m.split('-'); const d = new Date(+p[0], (+p[1]) - 1 + n, 1); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'); };
        const pill = (paid, due) => paid ? '<span class="uam-tag labor">✅</span>'
            : (new Date().toISOString().slice(0, 10) > due ? '<span class="uam-tag phone">⚠️ বকেয়া</span>' : '<span class="uam-tag advance">⏳ বাকি</span>');
        const months = pfBillMonthsDash();
        dues.innerHTML = months.map(m => {
            const st = pay[m] || {};
            const pc = st.prov && typeof st.prov === 'object' ? Object.keys(st.prov).length : 0;
            return '<div class="tile" style="cursor:default"><span class="ic">🗓️</span><span><span class="v" style="font-size:15px">' + esc(m) + '</span><br>' +
                '<span class="l">সাইট প্রাপ্য ' + pill(!!st.income, addM(m, 1) + '-15') + ' due ' + addM(m, 1) + '-15<br>' +
                'প্রোভাইডার ' + pc + '/' + provs + ' দিয়েছি ' + pill(pc >= provs && provs > 0, addM(m, 2) + '-15') + ' due ' + addM(m, 2) + '-15</span></span></div>';
        }).join('');
    } catch (e) {
        if (hero) hero.innerHTML = '<div class="k">📊 কোম্পানির অবস্থা</div><div class="big">—</div><div class="sub2">❌ ' + esc(e.message) + '</div>';
        if (tiles) tiles.innerHTML = '';
        if (dues) dues.innerHTML = '<div class="hint">❌ ' + esc(e.message) + '</div>';
    }
}
console.log('Dashboard loaded');

/* ===== Monthly cycle timeline (site -> provider -> invoice -> payment) ===== */
let CYC = {months: []};
function cycEsc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function cycDueLabel(iso){
    if(!iso)return '';
    const mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const p=String(iso).split('-');
    return (p[2]||'')+' '+mn[(+p[1])-1]+' '+(p[0]||'');
}
function cycLate(iso){try{return new Date().toISOString().slice(0,10)>iso}catch(e){return false}}
async function cycLoad(){
    const box=document.getElementById('cycBox');
    if(!box)return;
    try{
        const r=await fetch('/api/cycle?back=2&fwd=1');const j=await r.json();
        CYC=j;
        cycRender();
    }catch(e){box.innerHTML='<div class="hint">'+cycEsc('লোড হয়নি — '+e.message)+'</div>'}
}
function cycTickBtn(m,k,on,prov){
    const id='cycb_'+m+'_'+(prov?('p_'+prov.replace(/[^a-z0-9]/gi,'')):'x');
    return '<button class="ghost" id="'+id+'" title="'+cycEsc('এই ধাপটা বদলাতে চাপুন')+'"'
      + ' style="padding:2px 8px;border-radius:8px;cursor:pointer;'
      + (on?'background:rgba(74,222,128,.22);border-color:rgba(74,222,128,.55);color:#86efac'
            :'background:rgba(148,163,184,.12);border-color:rgba(148,163,184,.35);color:#cbd5e1')
      + '" onclick="cycDo(\''+cycEsc(m)+'\',\''+cycEsc(k)+'\','+(prov?'\''+cycEsc(prov)+'\'':'null')+')">'
      + (on?'✅':'⬜')+'</button>';
}
function cycRender(){
    const box=document.getElementById('cycBox');
    if(!box||!CYC.months)return;
    if(!CYC.months.length){box.innerHTML='<div class="hint">কোনো মাস নেই</div>';return}
    let h='<div style="overflow:auto"><table style="width:100%;font-size:12.5px;border-collapse:collapse">';
    CYC.months.forEach(m=>{
        const en = dashIsEn();
        const provAllPaid=m.providers.length>0&&m.providers.every(p=>p.paid);
        const sitePill=m.sitePaid?'<span class="pill prov">✅ '+(m.sitePaidDate||(en?'Paid':'দিয়েছে'))+'</span>'
            :(cycLate(m.siteDue)?'<span class="pill off">' + (en?'⚠️ Overdue':'⚠️ বকেয়া') + '</span>':'<span class="pill site">' + (en?'⏳ Pending':'⏳ বাকি') + '</span>');
        const provPill=provAllPaid?'<span class="pill prov">' + (en?'✅ All Paid':'✅ সব দিয়েছি') + '</span>'
            :(cycLate(m.provDue)?'<span class="pill off">' + (en?'⚠️ Overdue':'⚠️ বকেয়া') + '</span>':'<span class="pill site">' + (en?'⏳ Pending':'⏳ বাকি') + '</span>');
        h+='<tr style="border-top:1px solid rgba(255,255,255,.12)">';
        h+='<td style="padding:8px 6px;white-space:nowrap"><b style="font-size:14px">'+cycEsc(m.name)+'</b>';
        if(m.providerSheet)h+='<div style="font-size:10.5px;opacity:.65;margin-top:2px">📄 Total T বানানো</div>';
        h+='</td><td style="padding:8px 6px">';
        m.steps.forEach(st=>{
            if(st.kind==='one'){
                h+='<div style="display:flex;align-items:center;gap:6px;margin:2px 0">'+cycTickBtn(m.month,st.key,st.done)
                  +'<span>'+cycEsc(st.label)+'</span>'
                  +(st.done&&st.date?'<small style="opacity:.6">'+cycEsc(st.date)+'</small>':'')+'</div>';
            }else{
                h+='<div style="display:flex;align-items:center;gap:6px;margin:2px 0">'
                  +'<span style="min-width:22px;text-align:center;font-weight:700">'+(st.total?(st.done+'/'+st.total):'0')+'</span>'
                  +'<span>'+cycEsc(st.label)+'</span></div>';
                (st.items||[]).forEach(it=>{
                    h+='<div style="display:flex;align-items:center;gap:5px;margin:1px 0 1px 22px">'
                      +cycTickBtn(m.month,'inv',it.done,it.provider)
                      +'<span style="opacity:.85">'+cycEsc(it.name||it.provider)+'</span>'
                      +(it.no?'<small style="opacity:.6">'+cycEsc(it.no)+'</small>':'')
                      +(it.amount?'<small style="opacity:.6">'+cycEsc(it.amount)+' AED</small>':'')
                      +'</div>';
                });
            }
        });
        h+='</td>';
        h+='<td style="padding:8px 6px;white-space:nowrap"><div style="opacity:.7;font-size:11px">' + (en ? 'Site will pay' : 'সাইট দেবে') + '</div>'
          +sitePill+'<div style="opacity:.6;font-size:10.5px;margin-top:2px">'+cycEsc(cycDueLabel(m.siteDue))+'</div></td>';
        h+='<td style="padding:8px 6px;white-space:nowrap"><div style="opacity:.7;font-size:11px">' + (en ? 'Bill to pay' : 'বিল দেব') + '</div>'
          +provPill+'<div style="opacity:.6;font-size:10.5px;margin-top:2px">'+cycEsc(cycDueLabel(m.provDue))+'</div></td>';
        h+='</tr>';
    });
    h+='</table></div>'
      +'<div class="hint" style="margin-top:8px">'
      +'সাইকেল: মাস M তে সাইটে লোক দেওয়া → M+1 তে সাইটের টাইমশিট → প্রোভাইডারের ইনভয়েস → '
      +'সাইটের টাকা M+1-15, প্রোভাইডারের বিল M+2-15</div>';
    box.innerHTML=h;
}
async function cycDo(month,key,provider){
    try{
        const r=await fetch('/api/cycle-toggle',{method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({month:month,key:key,provider:provider})});
        const j=await r.json();
        if(!j.ok)throw new Error(j.error);
        await cycLoad();
    }catch(e){alert('সেভ হয়নি: '+e.message)}
}
