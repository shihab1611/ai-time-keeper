/* Monthly Profit — separate tab, separate files (profit_rates.json / profit_exp.json) */
let PROFIT = {rates: {}, expenses: [], files: [], file: '', workers: [], pay: {}};
PROFIT._sRows = [];
PROFIT._cRows = [];

function pfCurMonth() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}
function pfN(x) {
    x = Math.round((+x || 0) * 100) / 100;
    return (x % 1 === 0) ? x : x.toFixed(2);
}
function pfMsg(t, ok) {
    const el = document.getElementById('pfMsg');
    if (!el) return;
    el.textContent = t;
    el.className = 'status' + (ok ? ' ok' : '');
}
// বিল মাস M → সাইট দেয় M+1 এর ১৫, প্রোভাইডারকে দেই M+2 এর ১৫
function pfAddMonths(ym, n) {
    const p = String(ym || '').split('-');
    const d = new Date(+p[0], (+p[1] || 1) - 1 + n, 15);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-15';
}
function pfDueLabel(iso) {
    const mn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const p = String(iso || '').split('-');
    return p[2] + ' ' + (mn[+p[1] - 1] || '') + ' ' + p[0];
}
function pfOverdue(iso) {
    try { return new Date().toISOString().slice(0, 10) > iso; } catch (e) { return false; }
}
function pfPayState(month) {
    const m = (PROFIT.pay || {})[month] || {};
    const obj = (x) => (x && typeof x === 'object') ? x : {};
    const one = (x) => (x && typeof x === 'object') ? {paid: !!x.paid, date: x.date || ''} : {paid: !!x, date: ''};
    const prov = {}, clear = {};
    Object.keys(obj(m.prov)).forEach(k => { prov[k] = one(m.prov[k]); });
    Object.keys(obj(m.clear)).forEach(k => { clear[k] = one(m.clear[k]); });
    return {income: one(m.income), clear: clear, prov: prov};
}
function pfToday() { try { return new Date().toISOString().slice(0, 10); } catch (e) { return ''; } }
function pfBillMonths() {
    const out = [];
    let m = '2026-09';
    const cur = pfCurMonth();
    while (m <= cur) {
        out.push(m);
        const q = m.split('-');
        const d = new Date(+q[0], (+q[1]) - 1 + 1, 1);
        m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }
    return out;
}
// M+1 মাসের শেষ দিন (ক্লিয়ার ডেডলাইন)
function pfMonthEnd(ym) {
    const p = String(ym || '').split('-');
    const d = new Date(+p[0], (+p[1] || 1) - 1 + 1, 0);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
async function pfSetPay(kind, provider, paid, date) {
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    try {
        const r = await fetch('/api/ws/profit-pay', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({month: month, kind: kind, provider: provider || '', paid: !!paid, date: date || ''})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'সেভ হয়নি');
        PROFIT.pay = r.pay || {};
        renderProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}

async function loadProfit() {
    const box = document.getElementById('pfIncome');
    if (box) box.innerHTML = '<div class="hint">লোড হচ্ছে…</div>';
    try {
        const mEl = document.getElementById('pfMonth');
        if (mEl && !mEl.value) mEl.value = '2026-09';
        const fEl = document.getElementById('pfFile');
        const want = (fEl && fEl.value) || '';
        const r = await fetch('/api/ws/profit' + (want ? '?file=' + encodeURIComponent(want) : ''));
        const j = await r.json();
        if (!j.ok) throw new Error(j.error || 'লোড হয়নি');
        PROFIT.rates = j.rates || {};
        PROFIT.expenses = j.expenses || [];
        PROFIT.files = j.files || [];
        PROFIT.file = j.file || '';
        PROFIT.workers = j.workers || [];
        PROFIT.srates = j.srates || {};
        PROFIT.duty = j.duty || {};
        PROFIT.pay = j.pay || {};
        if (fEl) {
            const cur = PROFIT.file;
            fEl.innerHTML = PROFIT.files.map(f =>
                '<option value="' + esc(f.file) + '">' + esc(f.file) + '</option>').join('') ||
                '<option value="">— ফাইল নেই —</option>';
            fEl.value = cur;
        }
        renderProfit();
        xAll(document.getElementById('ws8'));
    } catch (e) {
        if (box) box.innerHTML = '<div class="hint">❌ ' + esc(e.message) + '</div>';
    }
}

function renderProfit() {
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    const W = PROFIT.workers;

        // ---- Income: PER WORKER + site splits (duty ledger overrides site) ----
    const sRows = W.filter(w => (+w.hours || 0) > 0).sort((a, b) => (+b.hours || 0) - (+a.hours || 0));
    PROFIT._sRows = sRows;
    const dutyM = ((PROFIT.duty || {})[month]) || {};
    let totH = 0, totInc = 0, ratedH = 0;
    sRows.forEach(w => {
        w._sr = (w.srate != null) ? +w.srate : null;
        w._key = pfNorm(w.name);
        const rec = dutyM[w._key];
        w._splits = (rec && rec.splits) || null;
        if (w._splits) {
            w._inc = 0;
            w._splits.forEach(sp => { w._inc += (+sp.hours || 0) * (w._sr != null ? w._sr : 0); });
            w._inc = Math.round(w._inc * 100) / 100;
        } else {
            w._inc = (w._sr != null) ? Math.round((+w.hours) * w._sr * 100) / 100 : 0;
        }
        totH += (+w.hours || 0); totInc += w._inc;
        if (w._sr != null) ratedH += (+w.hours || 0);
    });

    const pay = pfPayState(month);
    const incDue = pfAddMonths(month, 1);
    const provDue = pfAddMonths(month, 2);
    const clearDue = pfMonthEnd(pfAddMonths(month, 1).slice(0, 7));
    const incP = pay.income || {paid: false, date: ''};
    const incPill = incP.paid ? '<span class="pill prov">\u2705 \u09aa\u09c7\u09df\u09c7\u099b\u09bf</span>' + (incP.date ? ' ' + esc(incP.date) : '')
        : (pfOverdue(incDue) ? '<span class="pill off">\u26a0\ufe0f \u09ac\u0995\u09c7\u09df\u09be (due ' + pfDueLabel(incDue) + ')</span>'
        : '<span class="pill site">\u23f3 \u09ac\u09be\u0995\u09bf (due ' + pfDueLabel(incDue) + ')</span>');;

    document.getElementById('pfIncome').innerHTML =
        '<div style="margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">' + incPill +
        (incP.paid
            ? '<button class="ghost" onclick="pfSetPay(\'income\',\'\',false,\'\')">↩️ পাইনি করো</button>'
            : '<input type="date" id="pfIncDate" value="' + pfToday() + '" style="width:auto;padding:8px 10px;border-radius:10px;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.12);color:var(--txt)">' +
              '<button class="ghost" onclick="pfSetPay(\'income\',\'\',true,document.getElementById(\'pfIncDate\').value)">✅ সাইট দিয়েছে</button>') + '</div>' +
        '<table><tr><th>লোক</th><th>সাইট (ভাগ)</th><th>ঘণ্টা</th><th>খরচ রেট</th><th>সাইট রেট/hr</th><th>পাবো (AED)</th><th></th></tr>' +
        (sRows.map((w, i) => {
            const sp = w._splits;
            const siteCell = sp
                ? sp.map(x => esc(x.site) + ' ' + pfN(x.hours) + 'h/' + pfN(x.days) + 'দিন').join(' + ')
                : esc(w.site || '—');
            const spH = sp ? sp.reduce((a, x) => a + (+x.hours || 0), 0) : (+w.hours || 0);
            const warn = (sp && Math.abs(spH - (+w.hours || 0)) > 0.01)
                ? ' <span class="pill off">⚠️ ' + pfN(spH) + '/' + pfN(w.hours) + '</span>' : '';
            return '<tr><td>' + esc(w.name) + '</td><td>' + siteCell + warn + '</td><td>' + pfN(w.hours) + '</td><td>' + pfN(w.rate) + '</td>' +
            '<td><input type="number" step="0.5" min="0" value="' + (w._sr != null ? w._sr : '') + '" placeholder="?" ' +
            'style="width:90px;padding:6px 8px" onchange="pfSaveSRateByIdx(' + i + ',this.value)"></td>' +
            '<td><b>' + pfN(w._inc) + '</b></td>' +
            '<td>' + (w._sr != null ? '<button class="ghost" onclick="pfDelSRateByIdx(' + i + ')">🗑️</button>' : '') +
            ' <button class="ghost" title="সাইট ভাগ (কে কোন সাইটে কত দিন)" onclick="pfDutyEdit(' + i + ')">🧾</button></td></tr>' +
            '<tr id="dutyEd' + i + '" style="display:none"><td colspan="7"><div id="dutyBox' + i + '"></div></td></tr>';
        }).join('') || '<tr><td colspan="7">ঘণ্টা নেই — Total T ফাইল দেখুন</td></tr>') +
        '<tr><td><b>মোট</b></td><td></td><td><b>' + pfN(totH) + '</b></td><td></td><td></td><td><b>' + pfN(totInc) + '</b></td><td></td></tr></table>' +
        (sRows.some(w => w._sr == null) ? '<div class="hint">⚠️ যার সাইট রেট বসানো নেই, তার ইনকাম ০ ধরা হয়েছে — ওপরে রেট লিখলেই সেভ হবে।</div>' : '') +
        '<div class="hint">🧾 = সাইট ভাগ — কে কোন সাইটে কত দিন/ঘণ্টা (পেমেন্টের প্রমাণ)।</div>';

// ---- Cost: group by provider ----
    const byProv = {};
    W.forEach(w => {
        const p = (w.provider || '').trim() || '(প্রোভাইডার নেই)';
        if (!byProv[p]) byProv[p] = {provider: p, hours: 0, gross: 0, adv: 0, gas: 0};
        byProv[p].hours += (+w.hours || 0);
        byProv[p].gross += (+w.total || 0);
        byProv[p].adv += (+w.adv || 0);
        byProv[p].gas += (+w.gas || 0);
    });
    const cRows = Object.values(byProv).sort((a, b) => b.gross - a.gross);
    PROFIT._cRows = cRows;
    let cH = 0, cG = 0, cA = 0, cGas = 0;
    cRows.forEach(r => { cH += r.hours; cG += r.gross; cA += r.adv; cGas += r.gas; });
    const netPay = Math.round((cG - cA) * 100) / 100;

    document.getElementById('pfCost').innerHTML =
        '<table><tr><th>প্রোভাইডার</th><th>ঘণ্টা</th><th>গ্রস (ঘণ্টা×রেট)</th><th>এডভান্স (দেওয়া)</th><th>গ্যাস</th><th>নিট দিতে হবে</th><th>দেওয়া?</th></tr>' +
        (cRows.map((r, i) => {
            const pP = ((pay.prov || {})[r.provider]) || {};
            const pC = ((pay.clear || {})[r.provider]) || {};
            const isP = !!pP.paid, isC = !!pC.paid;
            const cell = isP ? '<span class="pill prov">✅ দিয়েছি' + (pP.date ? ' ' + esc(pP.date) : '') + '</span>'
                : (isC ? '<span class="pill site">🧾 ক্লিয়ার' + (pC.date ? ' ' + esc(pC.date) : '') + '</span>'
                : (pfOverdue(clearDue) ? '<span class="pill off">⚠️ ক্লিয়ার বাকি</span>'
                : '<span class="pill site">⏳ বাকি</span>'));
            const dIn = '<input type="date" id="pfPayD' + i + '" value="' + pfToday() + '" style="width:auto;max-width:135px;padding:5px 7px;border-radius:9px;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.12);color:var(--txt);font-size:12px">';
            return '<tr><td>' + esc(r.provider) + '</td><td>' + pfN(r.hours) + '</td><td>' + pfN(r.gross) + '</td>' +
            '<td>' + pfN(r.adv) + '</td><td>' + pfN(r.gas) + '</td><td><b>' + pfN(r.gross - r.adv) + '</b></td>' +
            '<td>' + cell +
            ' <button class="ghost" style="padding:3px 9px" title="হিসাব ক্লিয়ার" onclick="pfSetClearProv(' + i + ',' + (isC ? 'false' : 'true') + ',' + (isC ? "''" : "document.getElementById(\'pfPayD' + i + '\').value") + ')">🧾</button>' +
            (isP ? ' <button class="ghost" style="padding:3px 9px" title="টাকা দিয়েছি" onclick="pfSetPayProv(' + i + ',false)">↩️</button>'
                 : ' ' + dIn + ' <button class="ghost" style="padding:3px 9px" title="টাকা দিয়েছি" onclick="pfSetPayProv(' + i + ',true,document.getElementById(\'pfPayD' + i + '\').value)">✅</button>') + '</td></tr>';
        }).join('') || '<tr><td colspan="7">ঘণ্টা নেই</td></tr>') +
        '<tr><td><b>মোট</b></td><td><b>' + pfN(cH) + '</b></td><td><b>' + pfN(cG) + '</b></td>' +
        '<td><b>' + pfN(cA) + '</b></td><td><b>' + pfN(cGas) + '</b></td><td><b>' + pfN(netPay) + '</b></td><td></td></tr></table>' +
        '<div class="hint">\u{1F9FE} \u0995\u09cd\u09b2\u09bf\u09df\u09be\u09b0: ' + pfDueLabel(clearDue) + ' \u09aa\u09b0\u09cd\u09af\u09a8\u09cd\u09a4 \u2022 \u2705 \u09aa\u09c7\u09ae\u09c7\u09a8\u09cd\u099f: ' + pfDueLabel(provDue) + ' \u09aa\u09b0\u09cd\u09af\u09a8\u09cd\u09a4</div>' +
        '<div class="hint">এডভান্স আগেই দেওয়া — তাই নিট = গ্রস − এডভান্স। মোট খরচে গ্রসই ধরা হয়।</div>';

    // ---- Other expenses for this month ----
    const ex = PROFIT.expenses.map((e, i) => Object.assign({idx: i}, e)).filter(e => (e.month || '') === month);
    const exTot = ex.reduce((s, e) => s + (+e.amount || 0), 0);
    document.getElementById('pfExp').innerHTML =
        '<table><tr><th>খরচ</th><th>টাকা</th><th></th></tr>' +
        (ex.map(e =>
            '<tr><td>' + esc(e.label) + '</td><td>' + pfN(e.amount) + '</td>' +
            '<td><button class="ghost" onclick="pfDelExp(' + e.idx + ')">🗑️</button></td></tr>'
        ).join('') || '<tr><td colspan="3">এই মাসে খরচ লেখা নেই</td></tr>') +
        '<tr><td><b>মোট</b></td><td><b>' + pfN(exTot) + '</b></td><td></td></tr></table>';

    // ---- Summary cards ----
    const profit = Math.round((totInc - cG - exTot) * 100) / 100;
    const card = (label, val, color) =>
        '<div style="flex:1;min-width:140px;border:1px solid rgba(255,255,255,.2);border-radius:14px;padding:12px;background:rgba(0,0,0,.25)">' +
        '<div style="font-size:12px;color:var(--mut)">' + label + '</div>' +
        '<div style="font-size:22px;font-weight:800;color:' + (color || 'var(--txt)') + '">' + pfN(val) + ' <span style="font-size:12px">AED</span></div></div>';
    document.getElementById('pfCards').innerHTML =
        card('💰 মোট ইনকাম', totInc, '#7dd3fc') +
        card('💸 প্রোভাইডার খরচ', cG, '#fbbf24') +
        card('🧾 অন্য খরচ', exTot, '#fda4af') +
        card('📈 নিট প্রফিট', profit, profit >= 0 ? '#4ade80' : '#f87171');
    document.getElementById('pfSum').textContent =
        (PROFIT.file ? PROFIT.file.split('/').pop() : 'ফাইল নেই') + ' • প্রফিট ' + pfN(profit) + ' AED';
    const nr = document.getElementById('pfNoRate');
    if (nr) nr.style.display = (sRows.some(w => w._sr == null) ? '' : 'none');
    pfRenderHist();
}
function pfRenderHist() {
    const box = document.getElementById('pfHist');
    if (!box) return;
    const W = PROFIT.workers || [];
    const provs = [];
    W.forEach(w => { const q = (w.provider || '').trim(); if (q && provs.indexOf(q) < 0) provs.push(q); });
    box.innerHTML = '<table><tr><th>বিল মাস</th><th>সাইট (due M+1•15)</th><th>প্রোভাইডার (due M+2•15)</th></tr>' +
        pfBillMonths().map(m => {
            const st = (PROFIT.pay || {})[m] || {};
            const inc = (st.income && typeof st.income === 'object') ? st.income : {paid: !!st.income, date: ''};
            const pv = (st.prov && typeof st.prov === 'object') ? st.prov : {};
            const one = (x) => (x && typeof x === 'object') ? {paid: !!x.paid, date: x.date || ''} : {paid: !!x, date: ''};
            const incCell = inc.paid
                ? '<span class="pill prov">✅ ' + esc(inc.date || '') + '</span>'
                : '<span class="pill site">⏳ বাকি</span>';
            const pvCell = provs.map(pp => {
                const v = one(pv[pp]);
                return '<div>' + (v.paid ? '✅' : '☐') + ' ' + esc(pp) + (v.paid && v.date ? ' <b>' + esc(v.date) + '</b>' : '') + '</div>';
            }).join('') || '—';
            return '<tr><td><b>' + esc(m) + '</b></td><td>' + incCell + '</td><td>' + pvCell + '</td></tr>';
        }).join('') + '</table>' +
        '<div class="hint">সেপ্টেম্বর ২০২৬ থেকে সাইকেল — প্রতি মাসে চলতে থাকে।</div>';
}

function pfNorm(s) { return String(s || '').toLowerCase().replace(/[^a-z]/g, ''); }
function pfDutyEdit(i) {
    const w = (PROFIT._sRows || [])[i];
    const row = document.getElementById('dutyEd' + i);
    const box = document.getElementById('dutyBox' + i);
    if (!w || !row || !box) return;
    if (row.style.display !== 'none') { row.style.display = 'none'; return; }
    const cur = w._splits || [{site: (w.site || ''), days: '', hours: w.hours}];
    box._rows = cur.map(x => ({site: x.site || '', days: x.days || '', hours: x.hours || ''}));
    pfDutyRender(i);
    row.style.display = '';
}
function pfDutyRender(i) {
    const w = (PROFIT._sRows || [])[i];
    const box = document.getElementById('dutyBox' + i);
    if (!w || !box || !box._rows) return;
    box.innerHTML = box._rows.map((r, j) =>
        '<div class="wa-row" style="margin:4px 0"><div><input placeholder="সাইট" value="' + esc(r.site) + '" data-j="' + j + '" data-k="site" class="dutyIn"></div>' +
        '<div style="max-width:90px"><input type="number" step="0.5" min="0" placeholder="দিন" value="' + esc(r.days) + '" data-j="' + j + '" data-k="days" class="dutyIn"></div>' +
        '<div style="max-width:100px"><input type="number" step="0.5" min="0" placeholder="ঘণ্টা" value="' + esc(r.hours) + '" data-j="' + j + '" data-k="hours" class="dutyIn"></div>' +
        '<div style="flex:0 0 auto"><button class="ghost" onclick="pfDutyRowDel(' + i + ',' + j + ')">✖</button></div></div>'
    ).join('') +
    '<div class="wa-row" style="margin-top:6px"><div style="flex:0 0 auto"><button class="ghost" onclick="pfDutyRowAdd(' + i + ')">➕ সাইট যোগ</button></div>' +
    '<div style="flex:0 0 auto"><button class="ghost primary" onclick="pfDutySave(' + i + ')">💾 সেভ</button></div>' +
    '<div style="flex:0 0 auto"><button class="ghost" onclick="pfDutyDel(' + i + ')">🗑️ ভাগ মুছুন</button></div></div>' +
    '<div class="hint">মোট ঘণ্টা Total T-এর সাথে মিলিয়ে লিখুন (এখন ' + pfN(w.hours) + 'h)। এটাই পেমেন্টের প্রমাণ।</div>';
    box.querySelectorAll('.dutyIn').forEach(inp => {
        inp.onchange = () => { box._rows[+inp.dataset.j][inp.dataset.k] = inp.value; };
    });
}
function pfDutyRowAdd(i) {
    const box = document.getElementById('dutyBox' + i);
    if (!box || !box._rows) return;
    box._rows.push({site: '', days: '', hours: ''});
    pfDutyRender(i);
}
function pfDutyRowDel(i, j) {
    const box = document.getElementById('dutyBox' + i);
    if (!box || !box._rows) return;
    box._rows.splice(j, 1);
    pfDutyRender(i);
}
async function pfDutySave(i) {
    const w = (PROFIT._sRows || [])[i];
    const box = document.getElementById('dutyBox' + i);
    if (!w || !box) return;
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    try {
        const r = await fetch('/api/ws/profit-duty', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({month: month, person: w.name, splits: box._rows})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'সেভ হয়নি');
        PROFIT.duty = r.duty || {};
        pfMsg('✅ সাইট ভাগ সেভ: ' + w.name, true);
        loadProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
async function pfDutyDel(i) {
    const w = (PROFIT._sRows || [])[i];
    if (!w) return;
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    try {
        const r = await fetch('/api/ws/profit-duty', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({month: month, person: w.name, del: true})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'মোছা হয়নি');
        PROFIT.duty = r.duty || {};
        pfMsg('🗑️ সাইট ভাগ মোছা', true);
        renderProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
async function pfSaveSRate(person, rate) {
    try {
        const r = await fetch('/api/ws/profit-srates', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({person: person, rate: parseFloat(rate)})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'সেভ হয়নি');
        PROFIT.srates = r.srates || {};
        pfMsg('✅ সাইট রেট সেভ: ' + person, true);
        loadProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
function pfSaveSRateByIdx(i, rate) {
    const w = (PROFIT._sRows || [])[i];
    if (w) pfSaveSRate(w.name, rate);
}
async function pfDelSRateByIdx(i) {
    const w = (PROFIT._sRows || [])[i];
    if (!w) return;
    try {
        const res = await fetch('/api/ws/profit-srates', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({person: w.name, del: true})
        }).then(r => r.json());
        if (!res.ok) throw new Error(res.error || 'মোছা হয়নি');
        PROFIT.srates = res.srates || {};
        pfMsg('🗑️ সাইট রেট মোছা: ' + w.name, true);
        loadProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
async function pfAddExp() {
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    const label = document.getElementById('pfExpLabel').value.trim();
    const amount = document.getElementById('pfExpAmt').value;
    try {
        const r = await fetch('/api/ws/profit-exp', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({month: month, label: label, amount: parseFloat(amount)})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'যোগ হয়নি');
        PROFIT.expenses = r.expenses || [];
        document.getElementById('pfExpLabel').value = '';
        document.getElementById('pfExpAmt').value = '';
        pfMsg('✅ খরচ যোগ হয়েছে', true);
        renderProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
function pfSetClearProv(i, cleared, date) {
    const r = (PROFIT._cRows || [])[i];
    if (r) pfSetPay('clear', r.provider, cleared, date);
}
function pfSetPayProv(i, paid, date) {
    const r = (PROFIT._cRows || [])[i];
    if (r) pfSetPay('prov', r.provider, paid, date);
}
async function pfDelExp(i) {
    try {
        const r = await fetch('/api/ws/profit-exp', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({del: i})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'মোছা হয়নি');
        PROFIT.expenses = r.expenses || [];
        renderProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}
async function pfQuickRoom() {
    const month = (document.getElementById('pfMonth') || {}).value || pfCurMonth();
    if (PROFIT.expenses.some(e => e.month === month && /রুম|room/i.test(e.label || ''))) {
        pfMsg('⚠️ এই মাসে রুম ভাড়া আগেই আছে');
        return;
    }
    try {
        const r = await fetch('/api/ws/profit-exp', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({month: month, label: 'রুম ভাড়া (৬ জন)', amount: 1000})
        }).then(r => r.json());
        if (!r.ok) throw new Error(r.error || 'যোগ হয়নি');
        PROFIT.expenses = r.expenses || [];
        pfMsg('✅ রুম ভাড়া ১০০০ যোগ হয়েছে (' + month + ')', true);
        renderProfit();
    } catch (e) { pfMsg('❌ ' + e.message); }
}

console.log('Profit module loaded');
