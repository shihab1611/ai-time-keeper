"""Re-import: read a checked/edited Total T file back into the Data sheet.

The Data sheet stays the single source of truth. Flow:
    Data sheet -> Generate -> you check & fix the copy -> Re-import -> Data sheet
"""
import copy
import re

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from generator import (GRAND_SHEET_NAMES, locate_data_table, preview_total_sheet,
                       save_data_sheet, ZERO_TOKENS)

DAY_ROW0 = 4          # row 4 == day 1
DAY_ROW1 = 34         # row 34 == day 31
TOTAL_ROW = 35


def _txt(v):
    return " ".join(str(v or "").split())


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace(",", "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _norm(s):
    s = re.sub(r"\s*\(.*", "", str(s or ""))
    s = re.sub(r"^(md|mohammad)\s+", "", s.strip(), flags=re.I)
    return re.sub(r"[^a-z]", "", s.lower())


def _day_value(v):
    """Turn a Total T day cell back into a Data-sheet day value."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return v
    s = _txt(v)
    if not s:
        return None
    if s.upper() in ("SUNDAY", "SUN"):
        return "S"
    if s.upper() == "A":
        return "A"
    if s.upper() in ZERO_TOKENS:
        return None
    n = _num(s)
    return n if n is not None else s


def _provider_from_title(sheet_title):
    """'TIME SHEET ... SUPPLY LABOURS (Mr.ABZOL)' -> 'Mr.Abzol'."""
    t = _txt(sheet_title)
    m = re.search(r"\(([^()]*)\)\s*$", t)
    if not m:
        return ""
    raw = _txt(m.group(1))
    if not raw:
        return ""
    # MR.ABZOL -> Mr.Abzol ; NUR -> Mr.Nur ; SOMUJ -> Mr.Somuj
    if "." in raw:
        head, tail = raw.split(".", 1)
        return _txt(head.capitalize() + "." + tail.capitalize())
    up = raw.upper()
    aliases = {"NUR": "Mr.Nur", "JALIL": "Mr.Jalil", "ABZOL": "Mr.Abzol",
               "SOMUJ": "Mr.Somuj", "SAMUJ": "Mr.Samuj"}
    return aliases.get(up, raw)


def read_total_t(path):
    """Pull workers + days + grand numbers out of a Total T file."""
    prev = preview_total_sheet(path)
    grand = {}
    for g in prev.get("grand") or []:
        if g.get("t") == "w" and g.get("name"):
            grand[_norm(g["name"])] = {
                "name": _txt(g["name"]),
                "h": _num(g.get("h")),
                "rate": _num(g.get("rate")),
                "adv": _num(g.get("adv")),
                "gas": _num(g.get("gas")),
                "grand": _num(g.get("grand")),
            }
    workers = {}
    for sh in prev.get("sheets") or []:
        names = sh.get("workers") or []
        for ci, nm in enumerate(names):
            nm = _txt(nm)
            if not nm:
                continue
            days = []
            for row in sh.get("days") or []:
                vals = row.get("v") or []
                days.append(_day_value(vals[ci] if ci < len(vals) else None))
            # keep 31 slots so the grid lines up
            days = (days + [None] * 31)[:31]
            k = _norm(nm)
            prev_w = workers.get(k)
            if prev_w:
                for i, d in enumerate(days):
                    if d not in (None, "") and prev_w["days"][i] in (None, ""):
                        prev_w["days"][i] = d
            else:
                workers[k] = {"name": nm, "sheet": sh.get("name"),
                              "provider": _provider_from_title(sh.get("title") or sh.get("name")),
                              "days": days}
    return {"grand": grand, "workers": workers}


def reimport(total_t_path, data_path, apply_days=True, apply_grand=True,
             dry_run=False):
    """Copy worker/day/rate/advance/gas from a Total T back into the Data sheet.

    Never touches the master. Returns a change report so the UI can show
    exactly what was pulled back before anything is written.
    """
    src = read_total_t(total_t_path)

    grid_wb = load_workbook(data_path)
    sheet = grid_wb[grid_wb.sheetnames[0]]
    m = locate_data_table(sheet)
    if not m:
        grid_wb.close()
        raise ValueError("ডাটা শিটে লোকের সারি খুঁজে পাওয়া যায়নি")
    first = m["first_row"]

    # existing data-sheet rows, keyed by normalised name
    existing = {}
    for r in range(first, (sheet.max_row or 0) + 1):
        nm = _txt(sheet.cell(r, m["name"]).value)
        if nm:
            existing[_norm(nm)] = r

    changes = {"days": 0, "rate": 0, "advance": 0, "gas": 0,
               "newWorkers": [], "missing": []}

    def _set(rowno, colno, val):
        if not colno:
            return False
        cur = sheet.cell(rowno, colno).value
        if val is None:
            return False
        if str(val).strip() == "":
            return False
        try:
            same = abs(float(cur) - float(val)) < 1e-9
        except (TypeError, ValueError):
            same = str(cur or "").strip() == str(val).strip()
        if same:
            return False
        sheet.cell(rowno, colno).value = val
        return True

    for k, w in src["workers"].items():
        g = src["grand"].get(k, {})
        r = existing.get(k)
        if r is None:
            # worker exists in Total T but not in the data sheet -> append
            r = sheet.max_row + 1
            while r <= sheet.max_row:
                r += 1
            newrow = {}
            if m["sn"]:
                sheet.cell(r, m["sn"]).value = ""
            sheet.cell(r, m["name"]).value = w["name"]
            if m["provider"]:
                # prefer the provider written on the Total T sheet title
                pv = w.get("provider") or ""
                if not pv:
                    for rr in range(first, r):
                        cand = _txt(sheet.cell(rr, m["provider"]).value)
                        if cand:
                            pv = cand
                            break
                if pv:
                    sheet.cell(r, m["provider"]).value = pv
            existing[k] = r
            changes["newWorkers"].append(w["name"])

        if apply_days and m["days"]:
            for d, colno in m["days"].items():
                idx = d - 1
                if idx < len(w["days"]) and _set(r, colno, w["days"][idx]):
                    changes["days"] += 1
        if apply_grand:
            if _set(r, m.get("rate"), g.get("rate")):
                changes["rate"] += 1
            if _set(r, m.get("advance"), g.get("adv")):
                changes["advance"] += 1
            if _set(r, m.get("gas"), g.get("gas")):
                changes["gas"] += 1

    for k in existing:
        if k in src["workers"]:
            continue
        if k in src["grand"]:
            continue          # grand-only worker (e.g. Mr.Jalil) - nothing lost
        nm = _txt(sheet.cell(existing[k], m["name"]).value)
        if nm:
            changes["missing"].append(nm)

    if dry_run:
        grid_wb.close()
        return changes

    rows_out = get_rows_for_save(grid_wb, sheet, m)
    grid_wb.close()
    res = save_data_sheet(data_path, data_path, rows_out)
    changes.update(res)
    return changes


def get_rows_for_save(wb, sheet, m):
    """Build the row payload save_data_sheet expects, from an open workbook."""
    rows = []
    first = m["first_row"]
    for r in range(first, (sheet.max_row or 0) + 1):
        nm = _txt(sheet.cell(r, m["name"]).value)
        if not nm:
            continue
        days = []
        for d in range(1, 32):
            colno = m["days"].get(d)
            days.append(sheet.cell(r, colno).value if colno else None)
        row = {"sn": sheet.cell(r, m["sn"]).value if m["sn"] else None,
               "provider": _txt(sheet.cell(r, m["provider"]).value) if m["provider"] else "",
               "name": nm, "days": days, "rate": None, "advance": None,
               "gas": None, "fmt": {}}
        for fld, key in (("rate", "rate"), ("advance", "advance"), ("gas", "gas")):
            colno = m.get(key)
            row[fld] = sheet.cell(r, colno).value if colno else None
        rows.append(row)
    return rows