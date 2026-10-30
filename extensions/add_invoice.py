# -*- coding: utf-8 -*-
r"""Add Invoice extension — সম্পূর্ণ আলাদা মডিউল, ইঞ্জিনে কোনো পরিবর্তন ছাড়াই।

কোম্পানি/সাইটের নাম → মাস বেছে নিন → সব প্রোভাইডারের লোক এক লিস্টে → রেট বসান →
ঘণ্টা অটো (সেই মাসের ডেটা শিট) → ইনভয়েস (কোম্পানির নাম · Pay To = কোম্পানি/সাইট ·
Total = Σ(ঘণ্টা×রেট) · Amount in words) → Save → invoice\ ফোল্ডারে PDF (নম্বর চেইন চলবে)।

Time Keeper ইঞ্জিনে (app.py/generator.py) কোনো পরিবর্তন ছাড়াই চলে।
"""
import os
import re
import json
import time
import shutil

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import invoice_gen as G  # noqa: E402

BASE = G.BASE
CFG_FILE = os.path.join(BASE, "extensions", "add_invoice_config.json")
BACKUP_DIR = G.BACKUP_DIR
INVOICE_ROOT = os.path.join(BASE, "months")

MONTHS = G.MONTHS


# ---------------------------------------------------------------- config
def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"settings": {}, "company": {}, "clients": {}}


def save_cfg(cfg):
    if os.path.isfile(CFG_FILE):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            shutil.copy2(CFG_FILE, os.path.join(BACKUP_DIR, "ADDINVCFG." + ts + ".json"))
        except Exception:
            pass
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# ---------------------------------------------------------------- helpers
def _inv_dir(month, year):
    d = os.path.join(INVOICE_ROOT, "%s-%d" % (MONTHS.get(int(month), "JAN")[:3], int(year)), "invoice")
    os.makedirs(d, exist_ok=True)
    return d


def _next_inv_no(cfg, client_key, month, year):
    """ইনভয়েস নম্বর ধারাবাহিক চেইন — আলাদা ধারা (সেভ করা হয়, নইলে নম্বর থাকে না)।"""
    settings = cfg.setdefault("settings", {})
    assigned = settings.get("assigned", {}) if isinstance(settings.get("assigned"), dict) else {}
    skey = "%s|%s|%s" % (client_key, month, year)
    changed = False
    if skey in assigned:
        inv_no = int(assigned[skey])
    else:
        inv_no = int(settings.get("invoice_start_no", 1))
        if inv_no > 1000:
            inv_no = 1
        assigned[skey] = inv_no
        settings["assigned"] = assigned
        settings["invoice_start_no"] = inv_no + 1
        changed = True
    if changed:
        try:
            save_cfg(cfg)          # নম্বর চেইন স্থায়ী রাখতে — নইলে প্রতিবার 01
        except Exception:
            pass
    return "%02d" % inv_no


def _all_workers(month, year):
    """সব প্রোভাইডারের লোক এক মিশ্রিত লিস্টে — নির্দিষ্ট মাসের ডাটা শিট থেকে।"""
    try:
        ds_path, prov_workers, prov_order = G.read_data_sheet(month=month, year=year)
    except Exception:
        ds_path, prov_workers, prov_order = None, {}, []
    # আর্কাইভ ফলব্যাক: লাইভ শিটে সব ঘণ্টা খালি হলে মাস ফোল্ডার থেকে পড়া
    if prov_workers and all(sum(w["hours"] for w in ws_list) == 0
                            for ws_list in prov_workers.values()):
        try:
            _, arc_workers, arc_order = G.read_data_sheet(month=month, year=year,
                                                          source="archive")
            if arc_workers and any(sum(w["hours"] for w in ws_list)
                                   for ws_list in arc_workers.values()):
                prov_workers, prov_order = arc_workers, arc_order
        except Exception:
            pass
    all_workers = []
    for pn in prov_order:
        for w in prov_workers.get(pn, []):
            all_workers.append({
                "name": w["name"],
                "hours": w["hours"],
                "rate": w["rate"],
                "gas": w["gas"],
                "provider": pn,
            })
    return all_workers


# ---------------------------------------------------------------- builder
def build_add_invoice(client_key, client_name, client_address, month=None, year=None,
                      rates=None):
    """rates: {worker_name: rate} — ব্যবহারকারীর দিয়া রেট।"""
    cfg = load_cfg()
    settings = cfg.get("settings", {})
    comp = cfg.get("company") or {}
    # কোম্পানির তথ্য নিজের কনফিগে না থাকলে পেমেন্ট-স্টেটমেন্ট কনফিগ থেকে (হেডার খালি হয় না)
    if not (comp.get("name") or comp.get("contact") or comp.get("email")):
        try:
            comp = G.load_cfg().get("company") or comp
        except Exception:
            pass
    clients = cfg.get("clients", {})

    # ডিফল্ট মাস = ডেটা শিটের মাস
    dm, dy = G.data_month_year()
    m = int(month) if month else dm
    y = int(year) if year else dy

    now = time.localtime()
    date_s = "%02d %s %d" % (now.tm_mday, MONTHS.get(now.tm_mon, ""), now.tm_year)

    inv_no = _next_inv_no(cfg, client_key, m, y)

    all_workers = _all_workers(m, y)

    # সিলেক্ট করা ওয়ার্কারদের শুধু রাখব (রেটস ডিক্টের কি অনুযায়ী)
    selected_names = list(rates.keys()) if rates else []
    workers = []
    total_amt = 0.0
    for w in all_workers:
        if w["name"] not in selected_names:
            continue
        rate = float(rates.get(w["name"], w["rate"] or 0))
        amt = round(w["hours"] * rate, 2)
        total_amt += amt
        workers.append({
            "sl": len(workers) + 1,
            "name": w["name"],
            "hours": w["hours"],
            "rate": rate,
            "amount": amt,
        })

    net = round(total_amt, 2)
    warn = ""
    if selected_names and not workers:
        raise ValueError("সিলেক্ট করা কোনো ওয়ার্কার ডাটা শিটে মেলেনি — আবার 🔄 লোড ওয়ার্কার চাপুন")
    if workers and all(w["hours"] == 0 for w in workers):
        warn = "⚠️ এই মাসের ডাটা শিটে ঘণ্টা খালি — নির্বাচিত মাস ঠিক আছে কিনা দেখুন"
    return {
        "ok": True,
        "invoice_no": inv_no,
        "date": date_s,
        "month": m,
        "month_name": MONTHS.get(m, ""),
        "year": y,
        "warn": warn,
        "client_key": client_key,
        "client_name": client_name,
        "client_address": client_address,
        # UI/PDF উভয়েই client/address কী চায় — একই মান দুই নামে দিই
        "client": client_name,
        "address": client_address,
        "company": comp,
        "workers": workers,
        "total": net,
        "gas": 0.0,
        "advance": 0.0,
        "net": net,
        "in_words": G.amount_words(net),
        "from_name": comp.get("name", ""),
    }


def save_add_invoice_pdf(client_key, client_name, client_address, month, year, rates):
    data = build_add_invoice(client_key, client_name, client_address, month, year, rates)
    # মাসের নাম থেকে সংখ্যা খুঁজে বের করা
    mnum = [k for k, v in MONTHS.items() if v == data["month_name"]]
    out_dir = _inv_dir(mnum[0] if mnum else 1, data["year"])
    safe = re.sub(r"[^\w\s-]", "", str(client_name or client_key)).strip().replace(" ", "_")
    fname = "%s-%s.pdf" % (data["invoice_no"], safe or "invoice")
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
        return {}
    try:
        p = json.loads(raw)
        return p if isinstance(p, dict) else {}
    except ValueError:
        return {}


def api_build(handler, path, q):
    """প্রিভিউ — কোম্পানি ইনভয়েস ডেটা রিটার্ন করে।"""
    try:
        client_key = str(_q1(q, "client_key", "") or "").strip()
        client_name = str(_q1(q, "client_name", "") or "").strip()
        client_address = str(_q1(q, "client_address", "") or "").strip()
        month = _q1(q, "month", "") or None
        year = _q1(q, "year", "") or None
        rates = _parse_rates(_q1(q, "rates", ""))
        if not client_key:
            handler._json({"ok": False, "error": "কোম্পানি/সাইটের নাম দিন"}, 400)
            return
        data = build_add_invoice(client_key, client_name, client_address, month, year, rates)
        handler._json(data)
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_providers(handler, path, q):
    """সব প্রোভাইডারের লোকের লিস্ট (মিশ্রিত) — রেটসহ।"""
    try:
        month = _q1(q, "month", "") or None
        year = _q1(q, "year", "") or None
        dm, dy = G.data_month_year()
        m = int(month) if month else dm
        y = int(year) if year else dy
        all_workers = _all_workers(m, y)
        # ডুপ্লিকেট নাম সরিয়ে distinct worker লিস্ট
        seen = set()
        distinct = []
        for w in all_workers:
            key = w["name"].strip().lower()
            if key not in seen:
                seen.add(key)
                distinct.append({
                    "name": w["name"],
                    "hours": w["hours"],
                    "rate": w["rate"],
                    "provider": w["provider"],
                })
        handler._json({"ok": True, "workers": distinct,
                       "data_month": m, "data_year": y,
                       "month_name": MONTHS.get(m, ""),
                       "month_names": MONTHS})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_save_one(handler, path, body):
    """প্রিভিউ থেকে [সেভ] চাপলে — একই ইনভয়েস PDF সেভ।"""
    try:
        client_key = str(body.get("client_key", "") or "").strip()
        client_name = str(body.get("client_name", "") or "").strip()
        client_address = str(body.get("client_address", "") or "").strip()
        month = int(body.get("month") or 0) or None
        year = int(body.get("year") or 0) or None
        rates = body.get("rates") if isinstance(body.get("rates"), dict) else {}
        if not client_key:
            handler._json({"ok": False, "error": "কোম্পানি/সাইটের নাম দিন"}, 400)
            return
        data, out_dir, fname = save_add_invoice_pdf(client_key, client_name, client_address,
                                                    month, year, rates)
        handler._json({"ok": True, "file": fname, "dir": out_dir,
                       "invoice_no": data["invoice_no"]})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_save_cfg(handler, path, body):
    """কোম্পানি/সেটিংস কনফিগ সেভ।"""
    try:
        cfg = load_cfg()
        comp = body.get("company")
        if isinstance(comp, dict):
            cfg["company"] = comp
        clients = body.get("clients")
        if isinstance(clients, dict):
            cfg["clients"] = clients
        sett = body.get("settings")
        if isinstance(sett, dict):
            cfg["settings"] = sett
        save_cfg(cfg)
        handler._json({"ok": True})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


GET_ROUTES = {
    "/api/ws/add-invoice": api_build,
    "/api/ws/add-invoice-providers": api_providers,
}
POST_ROUTES = {
    "/api/ws/add-invoice-save-one": api_save_one,
    "/api/ws/add-invoice-save-pdf": api_save_one,
    "/api/ws/add-invoice-config": api_save_cfg,
}
