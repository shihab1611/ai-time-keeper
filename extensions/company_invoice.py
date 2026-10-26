# -*- coding: utf-8 -*-
"""Company Invoice extension.

Data Sheet থেকে সেই সাইটের ক্লায়েন্ট কোম্পানির জন্য ইনভয়েস বানায়।
- একই Data Sheet (একই লোক, একই ঘণ্টা)
- ক্লায়েন্টের আলাদা/বেশি Unit Price (প্রোভাইডার ৬ হলে কোম্পানি ৮)
- ADVANCE ও GAS থাকে না — শুধু ঘণ্টা × রেট = বিল
- ইনভয়েস নম্বর ধারাবাহিক (আলাদা ধারা)
- সেভ:  months\\<MON-YEAR>\\invoice\\NN-ClientName.pdf

invoice_gen.py থেকে helper ব্যবহার করে। Time Keeper ইঞ্জিনে কোনো পরিবর্তন নেই।
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import invoice_gen as G  # noqa: E402

BASE = G.BASE
CFG_FILE = os.path.join(BASE, "extensions", "company_invoice_config.json")
BACKUP_DIR = G.BACKUP_DIR


# ---------------------------------------------------------------- config
def load_ccfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"settings": {}, "company": {}, "providers": {}}


def save_ccfg(cfg):
    if os.path.isfile(CFG_FILE):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            import shutil
            shutil.copy2(CFG_FILE, os.path.join(BACKUP_DIR, "CINVCFG." + ts + ".json"))
        except Exception:
            pass
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- builder
def _resolve_ds_name(prov_key, prov_cfg, prov_order):
    ds_name = None
    for pn in prov_order:
        if G.norm_person(pn) == G.norm_person(prov_cfg.get("display", prov_key)):
            return pn
        if prov_key.replace("mr.", "") in G.norm_person(pn):
            return pn
    for pn in prov_order:
        d = G.norm_person(prov_cfg.get("display", ""))
        if d and d in G.norm_person(pn):
            return pn
    return None


def build_company_invoice(prov_key, month=None, year=None, rates=None):
    """rates: {worker_name: client_unit_price} — না দিলে প্রোভাইডারের default client_rate।"""
    ccfg = load_ccfg()
    pcfg_all = ccfg.get("providers", {})
    prov_cfg = pcfg_all.get(prov_key, {})
    comp = ccfg.get("company", {}) or G.load_cfg().get("company", {})

    # default month = data sheet's own month
    dm, dy = G.data_month_year()
    now = time.localtime()
    m = int(month) if month else dm
    y = int(year) if year else dy
    date_s = "%02d %s %d" % (now.tm_mday, G.MONTHS.get(now.tm_mon, ""), now.tm_year)

    ds_path, prov_workers, prov_order = G.read_data_sheet()
    ds_name = _resolve_ds_name(prov_key, prov_cfg, prov_order)
    if ds_name is None:
        raise ValueError("Data sheet-এ প্রোভাইডার পাওয়া যায়নি: " + str(prov_key))

    workers_raw = prov_workers.get(ds_name, [])
    default_rate = G._num(prov_cfg.get("client_rate"))

    workers = []
    total_amt = 0.0
    for i, w in enumerate(workers_raw, 1):
        rate = default_rate if default_rate > 0 else w["rate"]
        if rates and w["name"] in rates:
            try:
                rate = float(rates[w["name"]])
            except (TypeError, ValueError):
                pass
        amt = w["hours"] * rate
        total_amt += amt
        workers.append({"sl": i, "name": w["name"], "hours": w["hours"],
                        "rate": rate, "amount": amt})

    net = total_amt  # invoice: no gas, no advance

    # invoice number: separate continuous chain (1 -> 1000)
    settings = ccfg.setdefault("settings", {})
    assigned = settings.get("assigned", {}) if isinstance(settings.get("assigned"), dict) else {}
    skey = "%s|%s|%s" % (prov_key, m, y)
    if skey in assigned:
        inv_no = int(assigned[skey])
    else:
        inv_no = int(settings.get("invoice_start_no", 1))
        if inv_no > 1000:
            inv_no = 1
        assigned[skey] = inv_no
        settings["assigned"] = assigned
        settings["invoice_start_no"] = inv_no + 1
        save_ccfg(ccfg)

    return {
        "ok": True,
        "invoice_no": "%02d" % inv_no,
        "date": date_s,
        "month_name": G.MONTHS.get(m, ""),
        "year": y,
        "client": prov_cfg.get("client", ""),
        "address": prov_cfg.get("address", ""),
        "company": comp,
        "workers": workers,
        "total": round(total_amt, 2),
        "gas": 0.0,
        "advance": 0.0,
        "net": round(net, 2),
        "in_words": G.amount_words(net),
        "prov_key": prov_key,
        "prov_display": prov_cfg.get("display", prov_key),
        "from_name": comp.get("name", ""),
    }


# ---------------------------------------------------------------- save PDF
def _invoice_dir(month, year):
    d = os.path.join(BASE, "months", "%s-%d" % (G.MONTHS.get(int(month), "JAN")[:3], int(year)),
                     "invoice")
    os.makedirs(d, exist_ok=True)
    return d


def save_invoice_pdf(prov_key, month=None, year=None, rates=None):
    data = build_company_invoice(prov_key, month, year, rates=rates)
    mnum = [k for k, v in G.MONTHS.items() if v == data["month_name"]]
    out_dir = _invoice_dir(mnum[0] if mnum else 1, data["year"])
    fname = "%s-%s.pdf" % (data["invoice_no"], G._safe_name(data["client"] or data["prov_display"]))
    outp = os.path.join(out_dir, fname)
    G.make_pdf(data, outp, kind="invoice")
    return data, out_dir, fname


# ---------------------------------------------------------------- routes
def _q1(q, k, d=""):
    v = q.get(k, d)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else d
    return v


def _parse_rates(raw):
    raw = str(raw or "")
    if not raw:
        return None
    try:
        p = json.loads(raw)
        return p if isinstance(p, dict) else None
    except ValueError:
        return None


def api_build(handler, path, q):
    try:
        prov = str(_q1(q, "prov", "") or "").strip()
        if not prov:
            handler._json({"ok": False, "error": "প্রোভাইডার সিলেক্ট করুন"}, 400)
            return
        month = _q1(q, "month", "") or None
        year = _q1(q, "year", "") or None
        rates = _parse_rates(_q1(q, "rates", ""))
        data = build_company_invoice(prov, month, year, rates=rates)
        handler._json(data)
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_providers(handler, path, q):
    ccfg = load_ccfg()
    # company name falls back to statement config
    if not ccfg.get("company"):
        ccfg["company"] = G.load_cfg().get("company", {})
    ds_path, prov_workers, prov_order = G.read_data_sheet()
    dm, dy = G.data_month_year()
    out = []
    for pn in prov_order:
        key = None
        for k, v in ccfg.get("providers", {}).items():
            d = G.norm_person(v.get("display", ""))
            if d and d in G.norm_person(pn):
                key = k
                break
        if key is None:
            key = G.norm_person(pn).replace(" ", ".")
        pc = ccfg.get("providers", {}).get(key, {})
        out.append({"key": key, "data_name": pn,
                    "display": pc.get("display", pn),
                    "client": pc.get("client", ""),
                    "client_rate": pc.get("client_rate", 0),
                    "workers": len(prov_workers.get(pn, []))})
    handler._json({"ok": True, "providers": out,
                   "data_month": dm, "data_year": dy,
                   "settings": ccfg.get("settings", {}),
                   "company": ccfg.get("company", {}),
                   "clients": ccfg.get("providers", {})})


def api_save_one(handler, path, body):
    try:
        prov = str(body.get("prov", "") or "").strip()
        if not prov:
            handler._json({"ok": False, "error": "প্রোভাইডার সিলেক্ট করুন"}, 400)
            return
        month = int(body.get("month") or 0) or None
        year = int(body.get("year") or 0) or None
        rates = body.get("rates") if isinstance(body.get("rates"), dict) else None
        data, out_dir, fname = save_invoice_pdf(prov, month, year, rates=rates)
        handler._json({"ok": True, "file": fname, "dir": out_dir,
                       "invoice_no": data["invoice_no"]})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_save_all(handler, path, body):
    """Month Clear-এ কল — মাসের সব কোম্পানি ইনভয়েস PDF সেভ।"""
    try:
        month = int(body.get("month") or 0)
        year = int(body.get("year") or 0)
        if not (month and year):
            now = time.localtime()
            month, year = now.tm_mon, now.tm_year
        ccfg = load_ccfg()
        ds_path, prov_workers, prov_order = G.read_data_sheet()
        done, errors, seen = [], [], set()
        for pn in prov_order:
            key = None
            for k, v in ccfg.get("providers", {}).items():
                d = G.norm_person(v.get("display", ""))
                if d and d in G.norm_person(pn):
                    key = k
                    break
            if key is None:
                key = G.norm_person(pn).replace(" ", ".")
            if key in seen:
                continue
            seen.add(key)
            # skip providers with no client company set
            if not ccfg.get("providers", {}).get(key, {}).get("client"):
                continue
            try:
                data, out_dir, fname = save_invoice_pdf(key, month, year)
                if os.path.isfile(os.path.join(out_dir, fname)) and \
                        os.path.getsize(os.path.join(out_dir, fname)) > 0:
                    done.append(fname)
                else:
                    errors.append(key + ": ফাইল তৈরি হয়নি")
            except Exception as e:
                errors.append("%s: %s" % (key, e))
        handler._json({"ok": True, "saved": done, "count": len(done),
                       "errors": errors,
                       "dir": os.path.join(BASE, "months",
                                           "%s-%d" % (G.MONTHS.get(month, "JAN")[:3], year),
                                           "invoice")})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_save_cfg(handler, path, body):
    """ক্লায়েন্ট কোম্পানির নাম/ঠিকানা/ডিফল্ট রেট সেভ।"""
    ccfg = load_ccfg()
    provs = body.get("providers")
    if isinstance(provs, dict):
        ccfg["providers"] = provs
    comp = body.get("company")
    if isinstance(comp, dict):
        ccfg["company"] = comp
    sett = body.get("settings")
    if isinstance(sett, dict):
        ccfg["settings"] = sett
    save_ccfg(ccfg)
    handler._json({"ok": True})


GET_ROUTES = {
    "/api/ws/company-invoice": api_build,
    "/api/ws/company-invoice-providers": api_providers,
}
POST_ROUTES = {
    "/api/ws/company-invoice-save-one": api_save_one,
    "/api/ws/company-invoice-save-pdf": api_save_all,
    "/api/ws/company-invoice-config": api_save_cfg,
}
