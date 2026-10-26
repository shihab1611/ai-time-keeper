# -*- coding: utf-8 -*-
"""Invoice/Payment extension — কোম্পানি থেকে পেমেন্ট এলো/গেলোর হিসাব।
Time Keeper ইঞ্জিনে (app.py/generator.py) কোনো পরিবর্তন ছাড়াই চলে।
"""
import os
import json
import time
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV_FILE = os.path.join(BASE, "invoice_data.json")
BACKUP_DIR = os.path.join(BASE, "backup")


def _load():
    try:
        with open(INV_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _save(lst):
    if os.path.isfile(INV_FILE):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            shutil.copy2(INV_FILE, os.path.join(BACKUP_DIR, "INVOICE." + ts + ".json"))
        except Exception:
            pass
    with open(INV_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=1)


def get_all(handler, path, q):
    lst = _load()
    total_in = sum(float(x.get("amount") or 0) for x in lst if x.get("dir") == "in")
    total_out = sum(float(x.get("amount") or 0) for x in lst if x.get("dir") == "out")
    handler._json({
        "ok": True,
        "entries": lst,
        "totalIn": total_in,
        "totalOut": total_out,
        "balance": total_in - total_out,
    })


def add_entry(handler, path, body):
    try:
        amt = float(str(body.get("amount", "")).replace(",", "").strip())
    except Exception:
        handler._json({"ok": False, "error": "সঠিক টাকা লিখুন"}, 400)
        return
    if amt <= 0:
        handler._json({"ok": False, "error": "সঠিক টাকা লিখুন"}, 400)
        return
    d = str(body.get("date", "")).strip()[:20]
    if not d:
        d = time.strftime("%d/%m/%Y")
    direction = "out" if str(body.get("dir", "in")) == "out" else "in"
    desc = " ".join(str(body.get("desc", "")).split())[:500]
    lst = _load()
    lst.append({"amount": amt, "date": d, "dir": direction, "desc": desc})
    _save(lst)
    handler._json({"ok": True, "entries": lst})


def remove_entry(handler, path, body):
    try:
        idx = int(body.get("index", -1))
    except Exception:
        idx = -1
    lst = _load()
    if 0 <= idx < len(lst):
        removed = lst.pop(idx)
        _save(lst)
        handler._json({"ok": True, "removed": removed, "entries": lst})
    else:
        handler._json({"ok": False, "error": "এন্ট্রি পাওয়া যায়নি"}, 404)


GET_ROUTES = {"/api/ws/invoice": get_all}
POST_ROUTES = {
    "/api/ws/invoice-add": add_entry,
    "/api/ws/invoice-remove": remove_entry,
}
