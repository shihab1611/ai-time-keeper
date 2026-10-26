"""Bot memory + advance cross-check + monthly roll.

Everything here is stored in D:\\ai manager so it survives a Windows reinstall:
the folder lives on the D: drive, not in the Windows user profile.
"""
import json
import os
import re
import shutil
import time

from openpyxl import load_workbook

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "output")
MEM_FILE = os.path.join(BASE, "bot_memory.json")
PAST_DIR = os.path.join(OUT_DIR, "past months")

DEFAULTS = {
    "lang": "bn",
    "theme": "liquid-dark",
    "gridSize": 100,
    "autoBackup": True,
    "defMonth": 9,
    "defYear": 2026,
    "dataFile": "",
    "tmplFile": "",
    "profitMonth": "2026-09",
    "lastMonthRollover": "",
    "users": [],
}


# ---------------------------------------------------------------- memory ----
def mem_load():
    d = dict(DEFAULTS)
    try:
        with open(MEM_FILE, encoding="utf-8") as f:
            got = json.load(f)
        if isinstance(got, dict):
            d.update(got)
    except Exception:
        pass
    return d


def mem_save(d):
    """Merge into the memory file. Returns the stored dict."""
    cur = mem_load()
    cur.update(d or {})
    tmp = MEM_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=1)
        os.replace(tmp, MEM_FILE)
    except Exception:
        pass
    return cur


def mem_reset():
    try:
        if os.path.isfile(MEM_FILE):
            os.remove(MEM_FILE)
    except Exception:
        pass
    return dict(DEFAULTS)


# ------------------------------------------------------- advance parsing ----
def _num(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace(",", "").strip()
    try:
        return float(s) if s else 0
    except Exception:
        return 0


def _nm(v):
    return " ".join(str(v or "").split())


def _key(name):
    return re.sub(r"\s*\(.*", "", name).strip().lower()


def _cleared(st):
    s = st.lower()
    return ("paid" in s) or ("clear" in s)


def advance_people(adv_path):
    """Per-person advance totals from the Advance sheet.

    Mirrors the Workspace Advance tab parser so both views agree.
    Returns [{name, total, paid, balance, entries}].
    """
    wb = load_workbook(adv_path, data_only=True)
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb[wb.sheetnames[0]]
    people, order = {}, []

    blocks = []
    for c in range(1, (ws.max_column or 0) + 1):
        if _nm(ws.cell(4, c).value).lower() == "name":
            blocks.append((c, c + 1, c + 2, c + 3, c + 4))
    if not blocks:
        blocks = [(6, 7, 8, 9, 10)]

    for nc, ac, dc, sc, rc in blocks:
        cur = None
        for r in range(5, (ws.max_row or 0) + 1):
            name = _nm(ws.cell(r, nc).value)
            if not name:
                continue
            low = name.lower()
            if low.startswith("total") or low.startswith("grand balance"):
                cur = None
                continue
            k = _key(name)
            if not k:
                continue
            if k not in people:
                people[k] = {"name": re.sub(r"\s*\(.*", "", name).strip(),
                             "entries": [], "paid": 0.0, "balance": 0.0, "total": 0.0}
                order.append(k)
            cur = people[k]
            amt = _num(ws.cell(r, ac).value)
            dt = ws.cell(r, dc).value
            if hasattr(dt, "strftime"):
                dt = dt.date().isoformat()
            else:
                dt = str(dt or "").strip()
            st = _nm(ws.cell(r, sc).value)
            reason = _nm(ws.cell(r, rc).value)
            cur["entries"].append({"amount": amt, "date": dt,
                                   "status": st, "reason": reason})
            cur["total"] += amt
            if _cleared(st):
                cur["paid"] += amt
            else:
                cur["balance"] += amt
    wb.close()
    return [people[k] for k in order]


# ---------------------------------------------------- advance crosscheck ----
def _alias(name):
    """Normalise a name so 'MD SHIHAB' and 'Shihab' match."""
    s = re.sub(r"\s*\(.*", "", str(name or ""))
    s = re.sub(r"^(md|mohammad)\s+", "", s.strip(), flags=re.I)
    return re.sub(r"[^a-z]", "", s.lower())


def advance_check(data_path, adv_people, manual_match=None):
    """Compare each data-sheet worker's Advance cell with the real balance.

    Returns rows sorted worst-first: biggest balance that the sheet forgot.
    """
    from generator import get_data_grid

    grid = get_data_grid(data_path)
    data_rows = grid.get("rows") or []

    manual = {}
    for k, v in (manual_match or {}).items():
        manual[_alias(k)] = _alias(v)

    # Index each advance person under every name they might be called:
    #   "Shamsudduha"  -> shamsudhuha  + shamsuddin (from LABOR_MATCH)
    #   "Shihab"       -> shihab
    by_alias = {}
    for p in adv_people:
        a = _alias(p["name"])
        by_alias[a] = p
        if a in manual and manual[a] not in by_alias:
            by_alias[manual[a]] = p

    # First-token index, used ONLY when nothing else matches and the token is
    # unambiguous: "OSCAR NIYOYABISHATSE" -> "Oscar", "JUMA ..." -> "juma".
    by_first = {}
    for p in adv_people:
        tok = _alias(str(p["name"]).split()[0] if str(p["name"]).split() else "")
        if tok:
            by_first.setdefault(tok, []).append(p)

    def _find(nm):
        a = _alias(nm)
        if a in by_alias:
            return by_alias[a]
        # reverse LABOR_MATCH: sheet name is the canonical one
        for src, dst in manual.items():
            if dst == a and src in by_alias:
                return by_alias[src]
        hits = by_first.get(a[:1] and re.sub(r"[^a-z]", "", str(nm).split()[0].lower())) or []
        if len(hits) == 1:
            return hits[0]
        return None

    rows, missing_workers = [], []
    for w in data_rows:
        nm = str(w.get("name") or "").strip()
        if not nm:
            continue
        p = _find(nm)
        sheet_adv = _num(w.get("advance"))
        if p is None:
            # in the data sheet but has no advance entry at all
            missing_workers.append({"name": nm, "sheetAdvance": sheet_adv})
            rows.append({"name": nm, "sheetAdvance": sheet_adv,
                         "balance": 0.0, "diff": 0.0, "state": "no-record",
                         "provider": str(w.get("provider") or "")})
            continue
        bal = _num(p.get("balance"))
        diff = bal - sheet_adv
        state = "ok"
        if bal > 0 and sheet_adv <= 0:
            state = "missing"          # advance exists, sheet is blank
        elif diff > 0.009:
            state = "short"            # sheet has some, not all
        elif abs(diff) <= 0.009:
            state = "ok"
        rows.append({"name": nm, "sheetAdvance": sheet_adv, "balance": bal,
                     "diff": diff, "state": state,
                     "provider": str(w.get("provider") or ""),
                     "advanceName": p["name"]})

    rows.sort(key=lambda r: (-r["diff"], r["name"]))
    alerts = [r for r in rows if r["state"] in ("missing", "short")]
    return {"rows": rows, "alerts": alerts, "noRecord": missing_workers,
            "checked": len(rows)}


# ------------------------------------------------------------ month roll ----
def month_roll(data_path, month, year, archive_months=None):
    """Start a new month on the current data sheet.

    Keeps: worker list, provider, rate, advance, gas.
    Clears: every day cell, so the new month starts empty.
    Never touches the master copy.
    """
    from generator import get_data_grid, save_data_sheet

    grid = get_data_grid(data_path)
    rows = grid.get("rows") or []
    cleared = 0
    for w in rows:
        for d in range(31):
            if w.get("days") and w["days"][d] not in (None, ""):
                w["days"][d] = ""
                cleared += 1
        w["fmt"] = {}          # drop last month's red 'A' fills
    res = save_data_sheet(data_path, data_path, rows)

    archived = []
    if os.path.isdir(OUT_DIR):
        os.makedirs(PAST_DIR, exist_ok=True)
        want = set(archive_months or [f"{month:02d}-{year}"])
        for f in os.listdir(OUT_DIR):
            if not f.lower().endswith(".xlsx"):
                continue
            m = re.search(r"AUTO\s+(\d{2})-(\d{4})", f)
            if not m:
                continue
            tag = f"{m.group(1)}-{m.group(2)}"
            if tag not in want:
                continue
            src = os.path.join(OUT_DIR, f)
            dst = os.path.join(PAST_DIR, f)
            try:
                shutil.copy2(src, dst)          # copy, never move away
                archived.append(f)
            except Exception:
                pass
    return {"clearedCells": cleared, "workers": len(rows),
            "archived": archived, "pastDir": PAST_DIR, **res}


def month_label(m, y):
    names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
             "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    try:
        return f"{names[int(m) - 1]}-{y}"
    except Exception:
        return f"{m}-{y}"


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")