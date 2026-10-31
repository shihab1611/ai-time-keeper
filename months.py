"""Per-month folders for AI Time Keeper.Every month gets its own folder holding everything that belongs to it:

    months\\SEP-2026\\data sheet and total time sheet\\Data sheet sep-26.xlsx
    months\\SEP-2026\\data sheet and total time sheet\\Total T sheet AUTO 09-2026 বট.xlsx
    months\\SEP-2026\\statements\\     (খালি — শুধু স্টেটমেন্ট অপশনে সেভ চাপলে ফাইল আসে)
    months\\SEP-2026\\invoice\\         (খালি — শুধু ইনভয়েস অপশনে সেভ চাপলে ফাইল আসে)

month_clear() closes the current month and opens the next one. The master
template and the master data files are never written to -- everything here
is a copy. মাস ক্লিয়ার শুধু ডাটা শিট + টোটাল শিট সেভ করে; স্টেটমেন্ট/ইনভয়েস
ফোল্ডার তৈরি হয় খালি — ওগুলো কেবল নিজেদের অপশন থেকে সেভ করলেই ভরে।
"""
import os
import re
import shutil
import time

BASE = os.path.dirname(os.path.abspath(__file__))
MONTHS_DIR = os.path.join(BASE, "months")

MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# profit/cycle side-files that belong to a month
SIDE_FILES = ["profit_srates.json", "profit_duty.json", "profit_exp.json",
              "profit_pay.json", "profit_rates.json", "cycle.json"]

# মাস-ফোল্ডারের নির্ধারিত ৩টা সাব-ফোল্ডার
DATA_SUB = "data sheet and total time sheet"
STATEMENTS_SUB = "statements"
INVOICE_SUB = "invoice"


def month_label(m, y):
    """SEP-2026"""
    try:
        return "%s-%d" % (MONTH_ABBR[int(m) - 1], int(y))
    except (TypeError, ValueError, IndexError):
        return "%s-%s" % (m, y)


def next_month(m, y):
    m, y = int(m), int(y)
    return (1, y + 1) if m >= 12 else (m + 1, y)


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        d = re.search(r"(\d{4})", str(x))
        m = re.search(r"(\d{1,2})", str(x))
        return (int(d.group(1)), int(m.group(1))) if d and m else (0, 0)


def data_sheet_name(m, y):
    """9 / 2026 -> 'Data sheet sep-26.xlsx' (same style the user already uses)."""
    yy = str(int(y))[2:]
    return "Data sheet %s-%s.xlsx" % (MONTH_ABBR[int(m) - 1].lower(), yy)


def month_dir(m, y):
    return os.path.join(MONTHS_DIR, month_label(m, y))


def ensure_dir(m, y):
    d = month_dir(m, y)
    os.makedirs(d, exist_ok=True)
    return d


def list_months():
    """[{folder, label, month, year, files:[...], size}] newest month last."""
    out = []
    if not os.path.isdir(MONTHS_DIR):
        return out
    for name in sorted(os.listdir(MONTHS_DIR)):
        d = os.path.join(MONTHS_DIR, name)
        if not os.path.isdir(d):
            continue
        mm = re.match(r"^([A-Z]{3})-(\d{4})$", name)
        month = year = 0
        if mm:
            ab = mm.group(1)
            if ab in MONTH_ABBR:
                month = MONTH_ABBR.index(ab) + 1
            year = int(mm.group(2))
        files = []
        size = 0
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            size += st.st_size
            files.append({"name": f, "size": st.st_size,
                          "mtime": st.st_mtime, "xlsx": f.lower().endswith(".xlsx")})
        files.sort(key=lambda x: -x["mtime"])
        out.append({"folder": name, "label": name, "month": month, "year": year,
                    "files": files, "size": size,
                    "mtime": max([f["mtime"] for f in files], default=0)})
    out.sort(key=lambda x: (x["year"], x["month"]))
    return out


def _copy(src, dst):
    """Copy with a verification read-back; never silently half-writes."""
    if not os.path.isfile(src):
        return None
    shutil.copy2(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        raise IOError("কপি হয়নি: %s" % os.path.basename(src))
    with open(dst, "rb") as f:
        if f.read(2) != b"PK":
            raise IOError("কপি ঠিক নয় (zip নয়): %s" % os.path.basename(src))
    return dst


def _snapshot_side_files(dest, m, y):
    """profit/cycle json for this month, so the folder tells the whole story."""
    tag = "%04d-%02d" % (int(y), int(m))
    saved = []
    for fn in SIDE_FILES:
        src = os.path.join(BASE, fn)
        if not os.path.isfile(src):
            continue
        try:
            shutil.copy2(src, os.path.join(dest, "%s_%s" % (tag, fn)))
            saved.append("%s_%s" % (tag, fn))
        except Exception:
            pass
    return saved


def _readme(dest, m, y, data_name, total_name, workers, hours):
    txt = (
        "%s মাসের হিসাব\n"
        "%s\n\n"
        "ডেটা শিট : %s\n"
        "টোটাল শিট: %s\n"
        "সেভ করা : %s\n\n"
        "%s জন, মোট %s ঘণ্টা\n"
        "(এই ফোল্ডারে কোনো কিছু বট খোলে না -- শুধু সংরক্ষণের জন্য)\n"
    ) % (month_label(m, y), "-" * 30, data_name, total_name or "(তৈরি হয়নি)",
         time.strftime("%Y-%m-%d %H:%M:%S"), workers, hours)
    p = os.path.join(dest, "README.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)
    return "README.txt"


def month_clear(data_path, tmpl_path, month, year, do_generate=True,
                backup_fn=None):
    """Close `month/year` and start the next month on a brand-new data sheet.

    Saves into  months\\<ABBR>-<year>\\ :
        - the data sheet as it stands
        - the month's Total T sheet (generated here unless do_generate=False)
        - a snapshot of that month's profit/cycle json

    Then writes a fresh  <next month>  data sheet (days cleared, worker list,
    rate, advance and gas carried over) and returns a summary.
    """
    from generator import (get_data_grid, save_data_sheet, analyze_data_sheet,
                           generate_total_sheet)

    month, year = int(month), int(year)
    nm, ny = next_month(month, year)

    grid = get_data_grid(data_path)
    rows = grid.get("rows") or []
    workers = len(rows)
    try:
        info = analyze_data_sheet(data_path)
        hours = round(sum(float(w.get("total_h") or 0)
                          for w in info.get("workers") or []), 2)
    except Exception:
        hours = 0

    dest = ensure_dir(month, year)
    # ৩টা সাব-ফোল্ডার: ডাটা+টোটাল, স্টেটমেন্ট (খালি), ইনভয়েস (খালি)
    data_dir = os.path.join(dest, DATA_SUB)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(dest, STATEMENTS_SUB), exist_ok=True)
    os.makedirs(os.path.join(dest, INVOICE_SUB), exist_ok=True)
    saved = []

    # ---- 1. the month's data sheet ----
    if backup_fn:
        backup_fn(data_path)
    saved.append(_copy(data_path, os.path.join(data_dir, os.path.basename(data_path))))

    # ---- 2. the month's Total T (generated here so it is never forgotten) ----
    total_name = None
    if do_generate and workers:
        total_name = "Total T sheet AUTO %02d-%d বট.xlsx" % (month, year)
        tmp_out = os.path.join(data_dir, total_name)
        try:
            generate_total_sheet(data_path, tmpl_path, tmp_out, month, year)
            with open(tmp_out, "rb") as f:
                if f.read(2) != b"PK":
                    raise IOError("মোট শিট ঠিকমতো তৈরি হয়নি")
            # keep a copy in output\\ too, so the normal download list still works
            out_dir = os.path.join(BASE, "output")
            os.makedirs(out_dir, exist_ok=True)   # ক্লাউডে (Render) ফোল্ডারটা শুরুতেই থাকে না
            _copy(tmp_out, os.path.join(out_dir, total_name))
        except Exception:
            if os.path.isfile(tmp_out):
                try:
                    os.remove(tmp_out)
                except OSError:
                    pass
            raise

    # ---- 3. (ব্যবহারকারীর দাবি) অতিরিক্ত সাইড-ফাইল আর README ফোল্ডারে
    #      ফেলা হয় না — শুধু ডাটা শিট + টোটাল শিট।

    # ---- 4. the next month's data sheet: same people, empty days ----
    # নতুন মাসের শিট ইমপুট ফোল্ডারেই বসবে — ডাটা শিট আর মাস্টার সবসময় সেখানেই থাকে
    in_dir = os.path.join(BASE, "input output")
    if not os.path.isdir(in_dir):
        try:
            os.makedirs(in_dir, exist_ok=True)
        except OSError:
            in_dir = BASE                      # ফোল্ডার বানানো গেলে না

    def _taken(nm_, folder):
        return os.path.isfile(os.path.join(folder, nm_))

    new_name = data_sheet_name(nm, ny)
    # never clobber a month the user already started filling in
    # (দুই জায়গাই দেখি — পুরনো কপি বট-হোমেও থাকতে পারে)
    if _taken(new_name, in_dir) or _taken(new_name, BASE):
        n = 2
        while _taken(new_name.replace(".xlsx", "-%d.xlsx" % n), in_dir) or \
                _taken(new_name.replace(".xlsx", "-%d.xlsx" % n), BASE):
            n += 1
        new_name = new_name.replace(".xlsx", "-%d.xlsx" % n)
    new_path = os.path.join(in_dir, new_name)
    shutil.copy2(data_path, new_path)

    new_grid = get_data_grid(new_path)
    cleared = 0
    for w in (new_grid.get("rows") or []):
        for d in range(31):
            if w.get("days") and w["days"][d] not in (None, ""):
                w["days"][d] = ""
                cleared += 1
        w["fmt"] = {}                       # last month's red 'A' fills go away
    save_data_sheet(new_path, new_path, new_grid.get("rows") or [])

    # নতুন শিটের A1 তারিখও নতুন মাসের — detect_data_month() ওখান থেকেই হিন্ট নেয়
    try:
        from datetime import datetime
        from openpyxl import load_workbook as _lwb
        _wb = _lwb(new_path)
        _ws = _wb[_wb.sheetnames[0]]
        _ws.cell(1, 1).value = datetime(ny, nm, 1)
        _wb.save(new_path)
        _wb.close()
    except Exception:
        pass

    # (ব্যবহারকারীর দাবি) README.txt আর প্রফিট-JSON কপি এখন ফোল্ডারে ফেলা হয় না

    return {
        "closedMonth": month_label(month, year),
        "closedDir": dest,
        "files": [os.path.basename(x) for x in saved if x],
        "totalSheet": total_name,
        "workers": workers,
        "hours": hours,
        "clearedCells": cleared,
        "newFile": new_name,
        "newPath": new_path,
        "newMonth": month_label(nm, ny),
        "newMonthNum": nm,
        "newYear": ny,
    }
