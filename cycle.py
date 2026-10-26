"""Monthly cycle tracker.

The company's cycle for a bill month M:
  1. site time sheet arrives   (you type the data sheet yourself)
  2. you check it
  3. cleared
  4. provider time sheet made (auto-detected from the generated Total T)
  5. provider invoice received
  6. site pays us   -> due M+1 15th
  7. we pay provider -> due M+2 15th

Steps 1-3 and 5 are ticked by hand. Step 4 is detected automatically.
Steps 6-7 live in profit_pay.json (ws8) and are read, not duplicated here.
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "output")
CYCLE_FILE = os.path.join(BASE, "cycle.json")

# steps the user ticks; "sheet" is auto-detected and cannot be ticked
USER_STEPS = [
    ("siteFile", "\U0001F4E4 সাইটের ফাইল এসেছে"),
    ("checked", "\U0001F50E আমি চেক করেছি"),
    ("cleared", "\u2705 ক্লিয়ার হয়েছে"),
    ("inv", "\U0001F9FE প্রোভাইডার ইনভয়েস এসেছে"),
]

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ws8 stores providers under the grand-sheet reference text; show a short name.
_SHORT = {
    "refarenc of ( mr. nur )": "Mr.Nur",
    "refarenc of ( jalil )": "Mr.Jalil",
    "refarenc of (abzol )": "Mr.Abzol",
    "refarenc of somuj vai )": "Mr.Somuj",
    "mr.nur": "Mr.Nur", "mr.jalil": "Mr.Jalil",
    "mr.abzol": "Mr.Abzol", "mr.somuj": "Mr.Somuj", "mr.samuj": "Mr.Samuj",
    "mr.shihab": "Mr.Shihab",
    "mr.shibab": "Mr.Shibab",
    "mr.amin": "Mr.Amin",
}

PROVIDER_CONFIG_FILE = os.path.join(BASE, "provider_config.json")


def _config_short():
    """Short names derived from provider_config.json daily sheet names (trimmed)."""
    try:
        with open(PROVIDER_CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return {}
    if not isinstance(cfg, dict):
        return {}
    out = {}
    for key, entry in cfg.items():
        if not isinstance(entry, dict):
            continue
        sheet = entry.get("sheet")
        if sheet:
            out[str(key).strip().lower()] = str(sheet).strip()
    return out


# Config is the source of truth for provider short names; hardcoded map
# covers ref-string lookups and any key missing from config.
_SHORT.update(_config_short())


def short_name(raw):
    r = " ".join(str(raw or "").split())
    return _SHORT.get(r.lower(), r)


def load():
    try:
        with open(CYCLE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    tmp = CYCLE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CYCLE_FILE)
    except Exception:
        pass
    return d


def month_step(ym, n):
    """2026-09 + 1 month -> '2026-10'"""
    try:
        p = str(ym or "").split("-")
        y, m = int(p[0]), int(p[1])
        idx = (m - 1) + n
        return "%04d-%02d" % (y + idx // 12, idx % 12 + 1)
    except Exception:
        return ""


def month_name(ym):
    try:
        return MONTH_NAMES[int(str(ym).split("-")[1]) - 1] + " " + str(ym).split("-")[0]
    except Exception:
        return str(ym)


def due15(ym, n):
    m = month_step(ym, n)
    return (m + "-15") if m else ""


def generated_months():
    """Bill months the bot has already produced a Total T for."""
    out = {}
    try:
        names = os.listdir(OUT_DIR)
    except Exception:
        return out
    for f in names:
        m = re.search(r"AUTO\s+(\d{2})-(\d{4})", f)
        if m and f.lower().endswith(".xlsx"):
            out["%s-%s" % (m.group(2), m.group(1))] = f
    return out


def cycle_state(providers=None, pay=None, start="2026-09", months_back=3, months_fwd=1):
    """Everything the timeline needs for a window of bill months."""
    st = load()
    gen = generated_months()
    pay = pay if isinstance(pay, dict) else {}

    now = _today_ym()
    out_months = _range_months(start, months_back, months_fwd, now)

    rows = []
    for m in out_months:
        s = st.get(m) or {}
        stt = pay.get(m) or {}
        income = stt.get("income") or {}
        income = income if isinstance(income, dict) else {"paid": bool(income)}
        ppaid = stt.get("prov") or {}
        ppaid = ppaid if isinstance(ppaid, dict) else {}
        pclear = stt.get("clear") or {}
        pclear = pclear if isinstance(pclear, dict) else {}

        provs = []
        for p in (providers or []):
            q = str(p).strip()
            if q and q not in provs:
                provs.append(q)
        labels = {p: short_name(p) for p in provs}

        def one(x):
            return x if isinstance(x, dict) else {"paid": bool(x), "date": ""}

        site_due = due15(m, 1)
        prov_due = due15(m, 2)

        inv = s.get("inv") if isinstance(s.get("inv"), dict) else {}
        steps = []
        for key, label in USER_STEPS:
            if key == "inv":
                got = [(p, inv.get(p) or {}) for p in provs] if provs \
                    else [(k, v) for k, v in inv.items()]
                steps.append({"key": key, "label": label, "kind": "multi",
                              "done": sum(1 for _, v in got if (v or {}).get("done")),
                              "total": len(got),
                              "items": [{"provider": p,
                                         "name": labels.get(p) or short_name(p),
                                         "done": bool((v or {}).get("done")),
                                         "no": (v or {}).get("no", ""),
                                         "amount": (v or {}).get("amount"),
                                         "date": (v or {}).get("date", "")}
                                        for p, v in got]})
            else:
                v = s.get(key) or {}
                steps.append({"key": key, "label": label, "kind": "one",
                              "done": bool(v.get("done")),
                              "date": v.get("date", ""),
                              "note": v.get("note", "")})

        rows.append({
            "month": m,
            "name": month_name(m),
            "providerSheet": gen.get(m, ""),
            "steps": steps,
            "siteDue": site_due,
            "sitePaid": bool(income.get("paid")),
            "sitePaidDate": income.get("date", ""),
            "provDue": prov_due,
            "providers": [{"name": p,
                           "label": labels.get(p) or short_name(p),
                           "paid": bool(one(ppaid.get(p)).get("paid")),
                           "paidDate": one(ppaid.get(p)).get("date", ""),
                           "cleared": bool(one(pclear.get(p)).get("cleared")
                                           or one(pclear.get(p)).get("paid")),
                           "clearDate": (one(pclear.get(p)).get("date", "")
                                         or one(pclear.get(p)).get("clearedDate", ""))}
                          for p in provs],
        })
    return {"months": rows, "today": now}


def _today_ym():
    import datetime
    d = datetime.date.today()
    return "%04d-%02d" % (d.year, d.month)


def _range_months(start, back, fwd, today):
    """Walk back `back` months from `start` (never before the cycle began)."""
    seq = []
    m = start
    for _ in range(int(back)):
        prev = month_step(m, -1)
        if prev < start:          # do not go earlier than the cycle start
            break
        seq.insert(0, prev)
        m = prev
    seq.append(start)
    m = start
    for _ in range(int(fwd)):
        m = month_step(m, 1)
        seq.append(m)
    return seq


def toggle(ym, key, provider=None, value=None, note=None, no=None, amount=None):
    d = load()
    s = d.setdefault(ym, {})
    if key == "inv":
        inv = s.setdefault("inv", {})
        if provider:
            e = inv.setdefault(provider, {})
            e["done"] = (not e.get("done")) if value is None else bool(value)
            if no is not None:
                e["no"] = no
            if amount is not None:
                e["amount"] = amount
            e["date"] = _today() if e.get("done") else ""
    else:
        e = s.setdefault(key, {})
        e["done"] = (not e.get("done")) if value is None else bool(value)
        e["date"] = _today() if e.get("done") else ""
        if note is not None:
            e["note"] = note
    save(d)
    return s


def _today():
    import datetime
    return datetime.date.today().isoformat()