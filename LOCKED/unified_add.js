// Unified Add System - One click to add person to Advance + Labor + Provider
// Universal Search - Type name, see all details across Advance/Labor/Provider

// ===== Universal Search =====
async function universalSearch(query) {
    if (!query || query.trim().length < 2) return { results: [] };
    q = query.trim().toLowerCase();
    
    // Search across all systems
    const [advRes, labRes, phoneRes] = await Promise.all([
        fetch('/api/ws/advance').then(r => r.json()),
        fetch('/api/ws/labor').then(r => r.json()),
        fetch('/api/ws/phones').then(r => r.json())
    ]);
    
    const results = [];
    
    // Advance matches
    if (advRes.ok) {
        advRes.people.forEach(p => {
            if (p.name.toLowerCase().includes(q)) {
                results.push({
                    type: 'advance',
                    name: p.name,
                    subtitle: `Advance: ${p.total} AED | Paid: ${p.paid} | Balance: ${p.balance} | ${p.provider || 'No Provider'}`,
                    icon: '💰',
                    data: { advance: p }
                });
            }
        });
    }
    
    // Labor matches
    if (labRes.ok) {
        labRes.providers.forEach(b => {
            b.workers.forEach(w => {
                if (w.name.toLowerCase().includes(q)) {
                    results.push({
                        type: 'labor',
                        name: w.name,
                        subtitle: `Provider: ${b.provider} | ${w.off ? 'OFF' : w.site || 'No Site'} | Rate: ${w.rate || '?'} | Start: ${w.start || '?'}`,
                        icon: '👷',
                        data: { provider: b.provider, worker: w }
                    });
                }
            });
        });
    }
    
    // Phone matches
    if (phoneRes.ok) {
        Object.entries(phoneRes.phones).forEach(([name, phone]) => {
            if (name.toLowerCase().includes(q)) {
                results.push({
                    type: 'phone',
                    name: name,
                    subtitle: `Phone: ${phone}`,
                    icon: '📱',
                    data: { name, phone }
                });
            }
        });
    }
    
    // Deduplicate by name (merge types)
    const merged = {};
    results.forEach(r => {
        const key = r.name.toLowerCase();
        if (!merged[key]) merged[key] = { ...r, types: [r.type] };
        else merged[key].types.push(r.type);
    });
    
    return { results: Object.values(merged) };
}

// ===== Unified Add Modal (mode: 'search' | 'add') =====
async function showUnifiedAdd(mode) {
    mode = (mode === 'add') ? 'add' : 'search';
    // If already open, close it
    const existing = document.getElementById('unifiedAddModal');
    if (existing) { existing.remove(); return; }
    
    const modal = document.createElement('div');
    modal.id = 'unifiedAddModal';
    modal.className = 'uam-overlay';
    modal.innerHTML = `
        <div class="uam-panel">
            <div class="uam-header">
                <h3>➕ Unified Add — One Click Add Everywhere</h3>
                <button class="uam-close" onclick="this.closest('.uam-overlay').remove()">✕</button>
            </div>
            
            <div class="uam-search" id="uamSearchBox">
                <input type="text" id="uamSearch" placeholder="🔍 Type name to search across Advance/Labor/Phone..." autocomplete="off">
                <div id="uamSearchResults" class="uam-results"></div>
            </div>
            
            <div class="uam-form" id="uamForm" style="display:none">
                <h4>📝 Add New Person</h4>
                <div class="uam-row">
                    <div><label>Full Name *</label><input id="uaName" placeholder="Full Name"></div>
                    <div><label>Provider</label><select id="uaProvider" onchange="uaProvChanged()"><option value="">— Select —</option><option value="__new__">➕ নতুন প্রোভাইডার…</option></select><input id="uaNewProv" placeholder="নতুন প্রোভাইডারের নাম লিখুন" style="display:none;margin-top:6px" oninput="uaProvDefaults()"></div>
                </div>
                <div class="uam-row" id="uaProvConfigRow" style="display:none">
                    <div style="flex:1 1 200px"><label>ডেইলি শিটের নাম (ঐচ্ছিক)</label><input id="uaSheetName" placeholder="ডিফল্ট = প্রোভাইডার নাম"></div>
                    <div style="flex:1 1 260px"><label>গ্র্যান্ড হেডার (ঐচ্ছিক)</label><input id="uaGrandHeader" placeholder="ডিফল্ট = Refarenc of ( নাম )"></div>
                </div>
                <div class="uam-row">
                    <div><label>Phone</label><input id="uaPhone" placeholder="+971501234567"></div>
                    <div><label>Duty Start</label><input id="uaStart" type="date"></div>
                    <div style="flex:2 1 290px"><label>💬 Comment (ঐচ্ছিক)</label><input id="uaComment" placeholder="ডিউটির নোট / ইতিহাস — এক্সেল কমেন্টে জমা হবে"></div>
                    <div><label>Rate (AED/hr)</label><input id="uaRate" type="number" step="0.5" placeholder="7"></div>
                    <div><label>Site</label><input id="uaSite" placeholder="Al Maraj / DEBA / Al Khalij..." onchange="uaSiteRateHint()"></div>
                </div>
                <div class="uam-row">
                    <div><label>Site Rate — ওর জন্য/hr (ঐচ্ছিক)</label><input id="uaSiteRate" type="number" step="0.5" placeholder="খালি রাখা যায়"></div>
                </div>
                <div class="uam-row">
                    <div><label>Advance Amount</label><input id="uaAdvAmt" type="number" step="0.5" placeholder="0"></div>
                    <div><label>Advance Reason</label><input id="uaAdvReason" placeholder="Reason for advance"></div>
                    <div><label>Advance Status</label><select id="uaAdvStatus"><option value="">Pending</option><option value="paid">Paid</option></select></div>
                </div>
                <div class="uam-actions">
                    <button class="uam-btn primary" onclick="unifiedAddSubmit()">✅ Add to ALL (Advance + Labor + Phone)</button>
                    <button class="uam-btn" onclick="document.getElementById('unifiedAddModal').remove()">Cancel</button>
                </div>
            </div>
            
            <div id="uamStatus" class="uam-status"></div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Load data and populate the provider dropdown with existing providers
    await Promise.all([loadAdv(), loadLabor(), loadPhones()]);
    fillUaProviders();
    // Worker site rates in background (optional field hint only — empty is fine)
    try {
        if (typeof PROFIT !== 'undefined' && !Object.keys(PROFIT.srates || {}).length) {
            fetch('/api/ws/profit').then(r => r.json()).then(j => {
                if (j && j.ok) { PROFIT.srates = j.srates || {}; uaSiteRateHint(); }
            }).catch(() => {});
        }
    } catch (e) {}
    
    // Search logic
    let searchTimeout;
    const searchInput = document.getElementById('uamSearch');
    const resultsDiv = document.getElementById('uamSearchResults');
    const formDiv = document.getElementById('uamForm');
    
    searchInput.addEventListener('input', async (e) => {
        clearTimeout(searchTimeout);
        const q = e.target.value.trim();
        if (q.length < 2) {
            resultsDiv.innerHTML = '<div class="uam-hint">Type 2+ characters to search...</div>';
            return;
        }
        resultsDiv.innerHTML = '<div class="uam-loading">Searching...</div>';
        const res = await universalSearch(q);
        if (!res.results.length) {
            resultsDiv.innerHTML = '<div class="uam-hint">No matches found. Click below to add new.</div>';
            formDiv.style.display = 'block';
            return;
        }
        resultsDiv.innerHTML = res.results.map(r => `
            <div class="uam-result" onclick="uamShowCV('${r.name.replace(/'/g, "\\'")}')">
                <span class="uam-icon">${r.icon}</span>
                <div>
                    <strong>${r.name}</strong>
                    <small>${r.subtitle}</small>
                    ${r.types ? `<span class="uam-tags">${r.types.map(t=>`<span class="uam-tag ${t}">${t}</span>`).join('')}</span>` : ''}
                </div>
            </div>
        `).join('');
        formDiv.style.display = 'none';
    });
    
    // Focus search on open (add mode: blank form, no search box)
    if (mode === 'add') {
        document.getElementById('uamSearchBox').style.display = 'none';
        formDiv.style.display = 'block';
        setTimeout(() => document.getElementById('uaName').focus(), 100);
    } else {
        setTimeout(() => searchInput.focus(), 100);
    }
}

// Fill the modal's provider dropdown (existing providers + "new provider" option)
function fillUaProviders() {
    const sel = document.getElementById('uaProvider');
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">— Select —</option><option value="__new__">➕ নতুন প্রোভাইডার…</option>' +
        ((LABOR.providers || []).map(b => `<option value="${esc(b.provider)}">${esc(b.provider)}</option>`).join(''));
    if (cur && cur !== '__new__') sel.value = cur;
    uaProvChanged();
}

// Show/hide the new-provider text box and provider config fields
function uaProvChanged() {
    const sel = document.getElementById('uaProvider');
    const inp = document.getElementById('uaNewProv');
    const row = document.getElementById('uaProvConfigRow');
    if (!sel || !inp || !row) return;
    const isNew = sel.value === '__new__';
    inp.style.display = isNew ? 'block' : 'none';
    row.style.display = isNew ? 'flex' : 'none';
    if (isNew) {
        const eff = (document.getElementById('uaNewProv').value || sel.value).trim();
        const sheet = document.getElementById('uaSheetName');
        const head = document.getElementById('uaGrandHeader');
        if (sheet && !sheet.value) sheet.value = eff;
        if (head && !head.value) head.value = 'Refarenc of ( ' + eff + ' )';
    }
}

// Effective provider: typed new name wins when "new provider" is chosen
function uaEffProvider() {
    const sel = document.getElementById('uaProvider');
    if (!sel) return '';
    if (sel.value === '__new__') {
        const inp = document.getElementById('uaNewProv');
        return inp ? inp.value.trim() : '';
    }
    return sel.value.trim();
}

// Keep provider-config defaults in sync while typing a new provider name
function uaProvDefaults() {
    const sel = document.getElementById('uaProvider');
    if (!sel || sel.value !== '__new__') return;
    const eff = uaEffProvider();
    const sheet = document.getElementById('uaSheetName');
    const head = document.getElementById('uaGrandHeader');
    if (sheet && !sheet.value) sheet.value = eff;
    if (head && !head.value) head.value = 'Refarenc of ( ' + eff + ' )';
}

// Site-rate hint: this worker's known rate auto-fills the optional field (may stay empty)
function uaSiteRateHint() {
    try {
        if (typeof PROFIT === 'undefined' || !PROFIT.srates) return;
        const nm = document.getElementById('uaName').value.trim().toLowerCase().replace(/[^a-z]/g, '');
        const sr = document.getElementById('uaSiteRate');
        if (sr && !sr.value && nm) {
            for (const k of Object.keys(PROFIT.srates)) {
                if (k === nm && PROFIT.srates[k] && PROFIT.srates[k].rate) { sr.value = PROFIT.srates[k].rate; break; }
            }
        }
    } catch (e) {}
}

// Person CV — one card with EVERYTHING (site, start, hours, leaves, advance, provider, phone, profit)
async function uamShowCV(name) {
    const box = document.getElementById('uamSearchResults');
    box.innerHTML = '<div class="uam-loading">⏳ ডিটেইলস আনছি…</div>';
    try {
        await Promise.all([loadAdv(), loadLabor(), loadPhones()]);
        let pw = null, rates = {}, pfile = '', dutyAll = {};
        try {
            const pj = await fetch('/api/ws/profit').then(r => r.json());
            if (pj && pj.ok) {
                rates = pj.rates || {};
                dutyAll = pj.duty || {};
                const nk = name.toLowerCase().replace(/[^a-z]/g, '');
                const findW = (arr) => (arr || []).find(w => (w.name || '').toLowerCase().replace(/[^a-z]/g, '') === nk) || null;
                pw = findW(pj.workers);
                pfile = pj.file || '';
                // এই ফাইলে ঘণ্টা না থাকলে অন্য Total T ফাইলে খুঁজি
                if ((!pw || !pw.hours) && pj.files && pj.files.length > 1) {
                    for (const f of pj.files) {
                        if (f.file === pj.file) continue;
                        try {
                            const q = await fetch('/api/ws/profit?file=' + encodeURIComponent(f.file)).then(r => r.json());
                            if (q && q.ok) {
                                const w2 = findW(q.workers);
                                if (w2 && w2.hours) { pw = w2; pfile = q.file || f.file; break; }
                            }
                        } catch (e) {}
                    }
                }
                try { if (typeof PROFIT !== 'undefined') PROFIT.rates = rates; } catch (e) {}
            }
        } catch (e) {}
        const nk = name.toLowerCase().replace(/[^a-z]/g, '');
        const labProv = (LABOR.providers || []).find(b => b.workers.some(w => w.name.toLowerCase().replace(/[^a-z]/g, '') === nk));
        const lw = labProv ? labProv.workers.find(w => w.name.toLowerCase().replace(/[^a-z]/g, '') === nk) : null;
        const advP = (ADV.people || []).find(p => p.name.toLowerCase().replace(/[^a-z]/g, '') === nk);
        let phone = '';
        try { phone = PHONES[name] || PHONES[lw ? lw.name : ''] || ''; } catch (e) {}
        if (!phone) {
            try {
                const k = Object.keys(PHONES || {}).find(k => k.toLowerCase().replace(/[^a-z]/g, '') === nk);
                if (k) phone = PHONES[k];
            } catch (e) {}
        }
        const site = (lw && lw.site) || (pw && pw.site) || '';
        const start = (lw && lw.start) || '';
        const rate = (lw && lw.rate) || (pw && pw.rate) || '';
        const prov = labProv ? labProv.provider : ((advP && advP.provider) || '');
        const hours = pw ? (+pw.hours || 0) : 0;
        const absent = pw ? (+pw.absent || 0) : 0;
        const sick = pw ? (+pw.sick || 0) : 0;
        const gross = pw ? (+pw.total || 0) : Math.round(hours * (+rate || 0) * 100) / 100;
        const sRate = (pw && pw.srate != null) ? +pw.srate
            : (site && rates[site] != null ? +rates[site] : null);
        const income = (sRate != null) ? Math.round(hours * sRate * 100) / 100 : null;
        const myProfit = (income != null) ? Math.round((income - gross) * 100) / 100 : null;
        // duty splits (latest month containing this worker) — payment proof
        const initial = (name.trim()[0] || '?').toUpperCase();
        let dutyHtml = '';
        try {
            const months = Object.keys(dutyAll).sort().reverse();
            for (const mm of months) {
                const rec = ((dutyAll[mm] || {})[nk]);
                if (rec && rec.splits) {
                    dutyHtml = '<div class="hint" style="margin:0 0 8px">🧾 সাইট ভাগ (' + esc(mm) + '): ' +
                        rec.splits.map(x => esc(x.site) + ' ' + esc(x.hours) + 'h/' + esc(x.days) + 'দিন').join(' + ') + '</div>';
                    break;
                }
            }
        } catch (e) {}
        const cell = (label, val) => '<div class="cv-cell"><small>' + label + '</small><b>' + val + '</b></div>';
        const hist = (lw && lw.history && lw.history.length)
            ? '<div class="cv-hist">' + lw.history.map(h => '<div>📝 ' + esc(h) + '</div>').join('') + '</div>' : '';
        let waBtn = '';
        try {
            if (phone && typeof waLink === 'function' && waLink(phone, '')) {
                waBtn = '<button class="uam-btn" onclick="window.open(\'' + waLink(phone, 'আসসালামু আলাইকুম ' + name) + '\',\'_blank\')">💬 WhatsApp</button>';
            }
        } catch (e) {}
        box.innerHTML =
            '<div class="cv-head"><div class="cv-avatar">' + esc(initial) + '</div><div><h3>' + esc(name) + '</h3>' +
            '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">' +
            (prov ? '<span class="uam-tag labor">' + esc(prov) + '</span>' : '') +
            ((lw && lw.legal) ? '<span class="uam-tag phone">📜 ' + esc(lw.legal) + '</span>' : '') +
            (site ? '<span class="uam-tag advance">📍 ' + esc(site) + '</span>' : '') +
            ((lw && lw.off) ? '<span class="uam-tag phone">এখন বন্ধ</span>' : '') +
            '</div></div></div>' +
            '<div class="cv-grid">' +
            cell('📍 সাইট', esc(site || '—')) +
            cell('🗓 ডিউটি শুরু', esc(start || '—')) +
            cell('💲 রেট/hr (দেই)', rate !== '' && rate != null ? esc(rate) + ' AED' : '—') +
            cell('📱 ফোন', esc(phone || '—')) +
            cell('⏱ এই মাসের ঘণ্টা', hours ? hours : '—') +
            cell('🅰️ ছুটি (A)', absent) +
            cell('🤒 S', sick) +
            cell('💰 গ্রস (ঘণ্টা×রেট)', pfN2(gross) + ' AED') +
            cell('💸 এডভান্স বাকি', advP ? esc(advP.balance) + ' AED' : '—') +
            cell('📥 সাইট রেট/hr (পাই)', sRate != null ? esc(sRate) + ' AED' : 'রেট বসাননি') +
            cell('💵 ওর থেকে ইনকাম', income != null ? pfN2(income) + ' AED' : '—') +
            cell('📈 ওর থেকে লাভ', myProfit != null ? pfN2(myProfit) + ' AED' : '—') +
            '</div>' + (pfile ? '<div class="hint" style="margin:0 0 8px">📄 ঘণ্টা: ' + esc(pfile.split('/').pop()) + '</div>' : '') + dutyHtml + hist +
            '<div class="cv-actions">' +
            '<button class="uam-btn primary" onclick="uamSelectResult(\'' + name.replace(/'/g, "\\'") + '\')">✏️ Edit / ফর্মে নিন</button>' +
            waBtn +
            '<button class="uam-btn" onclick="document.getElementById(\'uamSearch\').value=\'\';document.getElementById(\'uamSearchResults\').innerHTML=\'\';document.getElementById(\'uamForm\').style.display=\'none\'">← ফিরে যান</button>' +
            '</div>';
        try { box.scrollIntoView({behavior: 'smooth', block: 'nearest'}); } catch (e) {}
    } catch (e) {
        box.innerHTML = '<div class="uam-hint">❌ ' + esc(e.message) + '</div>';
    }
}
function pfN2(x) {
    x = Math.round((+x || 0) * 100) / 100;
    return (x % 1 === 0) ? x : x.toFixed(2);
}

// Select a search result - pre-fill form
async function uamSelectResult(name) {
    document.getElementById('uamSearch').value = name;
    document.getElementById('uamSearchResults').innerHTML = '';
    
    // Ensure data is loaded
    await Promise.all([loadAdv(), loadLabor()]);
    
    // Populate the provider select with PROVIDER names (so .value will stick)
    fillUaProviders();
    const provSel = document.getElementById('uaProvider');
    
    const nameNorm = name.toLowerCase().replace(/[^a-z]/g, '');
    const advPerson = (ADV.people || []).find(p => p.name.toLowerCase().replace(/[^a-z]/g, '') === nameNorm);
    const labProv = (LABOR.providers || []).find(b => b.workers.some(w => w.name.toLowerCase().replace(/[^a-z]/g, '') === nameNorm));
    const labWorker = labProv ? labProv.workers.find(w => w.name.toLowerCase().replace(/[^a-z]/g, '') === nameNorm) : null;
    
    const form = document.getElementById('uamForm');
    form.style.display = 'block';
    
    document.getElementById('uaName').value = name;
    if (labProv) {
        provSel.value = labProv.provider;
    }
    if (labWorker) {
        document.getElementById('uaStart').value = labWorker.start || '';
        document.getElementById('uaRate').value = labWorker.rate || '';
        document.getElementById('uaSite').value = labWorker.site || '';
        const hist = (labWorker.history || []).join(' · ');
        document.getElementById('uaComment').value = hist || '';
    }
    if (advPerson) {
        document.getElementById('uaAdvAmt').value = advPerson.balance || 0;
    }
    uaSiteRateHint();
    document.getElementById('uamStatus').textContent = `✅ Loaded: ${name}`;
    document.getElementById('uamForm').scrollIntoView({behavior:'smooth'});
}

// Unified submit - adds to ALL systems
async function unifiedAddSubmit() {
    const name = document.getElementById('uaName').value.trim();
    const provider = uaEffProvider();
    const isNewProv = document.getElementById('uaProvider').value === '__new__';
    const phone = document.getElementById('uaPhone').value.trim();
    const start = document.getElementById('uaStart').value;
    const rate = document.getElementById('uaRate').value;
    const site = document.getElementById('uaSite').value.trim();
    const advAmt = document.getElementById('uaAdvAmt').value;
    const advReason = document.getElementById('uaAdvReason').value.trim();
    const advStatus = document.getElementById('uaAdvStatus').value;
    const comment = document.getElementById('uaComment').value.trim();
    
    const status = document.getElementById('uamStatus');
    status.className = 'uam-status';
    status.textContent = 'Saving...';
    
    if (!name) { status.textContent = '❌ Name required'; return; }
    if (isNewProv && !provider) { status.textContent = '❌ নতুন প্রোভাইডারের নাম লিখুন'; return; }
    if (comment && !provider) {
        status.textContent = '❌ কমেন্ট জমা হতে প্রোভাইডার বেছে নিন';
        return;
    }
    
    try {
        const results = [];
        const errors = [];
        
        // 1. Add to Advance
        if (document.getElementById('uaAdvAmt').value) {
            const advAmt = parseFloat(document.getElementById('uaAdvAmt').value);
            try {
                const r = await fetch('/api/ws/advance-add', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        person: name, amount: advAmt, date: new Date().toISOString().split('T')[0],
                        paid: false, reason: document.getElementById('uaAdvReason').value || 'New entry',
                        provider: provider
                    })
                }).then(r=>r.json());
                if (r.ok) results.push('Advance ✅'); else errors.push('Advance: ' + (r.error || 'failed'));
            } catch (e) { errors.push('Advance: ' + e.message); }
        }
        
        // 2. Add to Labor (with provider auto-create)
        if (provider) {
            try {
                const r = await fetch('/api/ws/labor-save', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        act: 'add', provider: provider, name: name,
                        start: start, rate: parseFloat(rate) || 0, site: site
                    })
                }).then(r=>r.json());
                if (r.ok) results.push('Labor ✅'); else errors.push('Labor: ' + (r.error || 'failed'));
                // 2b. ডিউটি স্টার্টের ঘরে কমেন্ট বসে (এক্সেল কমেন্ট = ডিউটির ইতিহাস)
                if (r.ok && comment) {
                    try {
                        const c = await fetch('/api/ws/labor-save', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ act: 'comment', col: r.col, row: r.row, text: comment })
                        }).then(x => x.json());
                        if (c.ok) results.push('💬 কমেন্ট ✅');
                        else errors.push('কমেন্ট: ' + (c.error || 'failed'));
                    } catch (e) { errors.push('কমেন্ট: ' + e.message); }
                }
            } catch (e) { errors.push('Labor: ' + e.message); }
        }
        
        // 3. Save Phone
        if (phone) {
            try {
                const r = await fetch('/api/ws/phones', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({person: name, set: phone})
                }).then(r=>r.json());
                if (r.ok) results.push('Phone ✅'); else errors.push('Phone: ' + (r.error || 'failed'));
            } catch (e) { errors.push('Phone: ' + e.message); }
        }
        
        // 3b. Register NEW provider in provider_config.json (dashboard -> generator)
        if (isNewProv && provider) {
            const sheetName = document.getElementById('uaSheetName') ? document.getElementById('uaSheetName').value.trim() : '';
            const grandHeader = document.getElementById('uaGrandHeader') ? document.getElementById('uaGrandHeader').value.trim() : '';
            try {
                const r = await fetch('/api/ws/provider-save', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        provider: provider,
                        sheet_name: sheetName || provider,
                        header_text: grandHeader || 'Refarenc of ( ' + provider + ' )'
                    })
                }).then(r=>r.json());
                if (r.ok) results.push('Provider Config ✅'); else errors.push('Provider Config: ' + (r.error || 'failed'));
            } catch (e) { errors.push('Provider Config: ' + e.message); }
        }

        // 4. Save Provider mapping
        if (provider) {
            try {
                const r = await fetch('/api/ws/labor-assign', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({person: name, provider: provider})
                }).then(r=>r.json());
                if (r.ok) results.push('Provider Mapping ✅'); else errors.push('Mapping: ' + (r.error || 'failed'));
            } catch (e) { errors.push('Mapping: ' + e.message); }
        }
        
        // 5. Save Site Rate for THIS WORKER (optional — empty is fine)
        const siteRateEl = document.getElementById('uaSiteRate');
        const siteRate = siteRateEl ? parseFloat(siteRateEl.value) : NaN;
        if (!isNaN(siteRate) && siteRate > 0) {
            try {
                const r = await fetch('/api/ws/profit-srates', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({person: name, rate: siteRate})
                }).then(r=>r.json());
                if (r.ok) {
                    results.push('Site Rate ✅');
                    try { if (typeof PROFIT !== 'undefined') PROFIT.srates = r.srates || PROFIT.srates; } catch (e) {}
                } else errors.push('Site Rate: ' + (r.error || 'failed'));
            } catch (e) { errors.push('Site Rate: ' + e.message); }
        }
        
        // Reload all
        await Promise.all([loadAdv(), loadLabor(), loadPhones()]);
        waFillSelects(); waRenderPhones();
        
        document.getElementById('unifiedAddModal').remove();
        if (errors.length) {
            showToast('⚠️ Added: ' + (results.join(', ') || 'none') + ' | ❌ ' + errors.join('; '));
        } else {
            showToast('✅ Added to ALL: ' + results.join(', '));
        }
    } catch (e) {
        status.className = 'uam-status error';
        status.textContent = '❌ ' + e.message;
    }
}

// Toast helper
function showToast(msg) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(()=>t.remove(), 4000);
}

// ===== Universal Search Button in Header =====
function addUniversalSearchButton() {
    const nav = document.querySelector('nav');
    if (!nav || document.getElementById('uniSearchBtn')) return;
    const btn = document.createElement('button');
    btn.id = 'uniSearchBtn';
    btn.className = 'ext';
    btn.onclick = showUnifiedAdd;
    btn.innerHTML = '🔍 Universal Search & Add';
    nav.appendChild(btn);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(addUniversalSearchButton, 500);
});

console.log('Unified Add System loaded');