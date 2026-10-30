# AI Time Keeper — local dashboard server (stdlib only)
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

# the folder this file lives in — that IS the bot's home, so the whole app can
# be copied anywhere and still find its own data/output/backup
BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "output")
# ব্যবহারকারীর ইনপুট ফোল্ডার — Data sheet + Total Master sheet এখানেই থাকে।
# বট এখান থেকেই ডেটা আর টেমপ্লেট খোঁজে, মাস্টার ফাইলে কখনো হাত দেয় না।
INPUT_DIR = os.path.join(BASE, "input output")
BACKUP_DIR = os.path.join(BASE, "backup")
CUSTOM_DIR = os.path.join(BASE, "custom")
DRIVE_DIR = r"C:\Users\Admin\OneDrive\Desktop\somuj vai"
ADV_DIR = os.path.join(DRIVE_DIR, "All Advance Sheets")
# The bot NEVER writes to the user's own file. It works on a clearly named
# copy that sits next to it, so the master sheet can only be touched by hand.
ADV_MASTER = "Advance sheet.xlsx"
ADV_BOT = "Advance sheet বট.xlsx"
ADV_FILE = os.path.join(ADV_DIR, ADV_BOT)


def advance_ready():
    """True if the bot's own working copy exists."""
    return os.path.isfile(ADV_FILE)


def advance_ensure():
    """Return the bot's working copy, recreating it from the master if missing.

    The master (Advance sheet.xlsx) is never written to by the bot.
    """
    if os.path.isfile(ADV_FILE):
        return ADV_FILE
    master = os.path.join(ADV_DIR, ADV_MASTER)
    if not os.path.isfile(master):
        raise FileNotFoundError(ADV_MASTER + " নেই")
    shutil.copy2(master, ADV_FILE)
    return ADV_FILE


# ---- Labor / duty sheet: who works for which provider, at which site ----
LABOR_DIR = os.path.join(DRIVE_DIR, "Labors Runing Duty in Comphany or Site")
LABOR_MASTER = "working in company Manpower 2.xlsx"
LABOR_BOT = "working in company Manpower 2 বট.xlsx"
LABOR_FILE = os.path.join(LABOR_DIR, LABOR_BOT)

# Names written differently in the advance sheet vs the labor sheet.
# Confirmed by the user: match these by hand.
LABOR_MATCH = {
    "shamsudhuha": "Shamsuddin",
    "shariful islam": "Shoriful",
}
# These are providers/references, not workers - they get their own group.
LABOR_NON_WORKER = {"nur vai", "noor vai take", "jalil"}

# Duty sheet-এর ছোট নাম -> আপনার আইনি/ফুল নাম।
# শুধু ডিউটি শিটে যারা আছে তারাই রাখা হয়েছে; বাকি (Faysal,
# KEMAL ABDELA GEBEWO) ডিউটিতে নেই বলে বাদ।
LABOR_LEGAL = {
    "nennu miah": "NENU",
    "abdur rahman": "ABDIREHMAN AREGA YASIN",
    "seyfu": "SEYFU JUNDI ADEM",
    "ermias gebrewold demissie": "ERMIAS GEBREWOLD DEMISSIE",
    "patrick gatoto": "PATRICK GATOTO",
    "nuradin fayo": "NURADIN FAYO",
    "aimable igiraneza": "Aimable Igiraneza",
    "abdul qadir": "ABDULKADIR EDASA NEGEWO",
    "yaw attah": "YAW ATTAH",
    "juma": "JUMA MWALIMU SWALEH",
    "oscar": "OSCAR NIYABISHATSE",
    "md shihab": "SHIHAB",
    "shoriful": "SHORIFUL SAIFUL",
    "md ambia": "Md Ambia",
    "hobibur rahman": "HOBIBUR RAHMAN",
    "alim uddin": "ALIM UDDIN",
    "aricho": "ARICHO",
}


def labor_ensure():
    """Bot copy of the labor sheet; recreated from the master if missing."""
    if not os.path.isfile(LABOR_FILE):
        master = os.path.join(LABOR_DIR, LABOR_MASTER)
        if not os.path.isfile(master):
            raise FileNotFoundError(LABOR_MASTER + " নেই")
        shutil.copy2(master, LABOR_FILE)
    preserve_snapshot(LABOR_FILE)
    return LABOR_FILE


# ---- openpyxl ছবি/ইঙ্ক মুছে ফেলে, তাই আগে সংরক্ষণ করে পরে ফিরিয়ে দিই ----
PARTS_DIR = os.path.join(BASE, "labor_parts")
PRESERVE_PARTS = [
    "xl/drawings/drawing1.xml",
    "xl/drawings/_rels/drawing1.xml.rels",
    "xl/ink/ink1.xml", "xl/ink/ink2.xml", "xl/ink/ink3.xml",
    "xl/media/image1.png", "xl/media/image2.png",
]
DRAW_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
DRAW_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def preserve_snapshot(src):
    """একবারই ছবি/ইঙ্ক অংশগুলোর নিজস্ব কপি রেখে দেয় (ফাইলে থাকতে যখন)।"""
    try:
        if os.path.isfile(os.path.join(PARTS_DIR, ".ok")):
            return
        import zipfile
        with zipfile.ZipFile(src) as z:
            names = set(z.namelist())
            if not all(p in names for p in PRESERVE_PARTS):
                return
            for p in PRESERVE_PARTS:
                fp = os.path.join(PARTS_DIR, p.replace("/", os.sep))
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "wb") as f:
                    f.write(z.read(p))
        with open(os.path.join(PARTS_DIR, ".ok"), "w") as f:
            f.write("ok")
    except Exception:
        pass


def restore_parts(dst):
    """openpyxl সেভ করার পর ছবি/ইঙ্ক ফিরিয়ে বসায়।"""
    if not os.path.isfile(os.path.join(PARTS_DIR, ".ok")):
        return False
    try:
        import zipfile
        import re as _re
        srcs = {}
        for p in PRESERVE_PARTS:
            fp = os.path.join(PARTS_DIR, p.replace("/", os.sep))
            if not os.path.isfile(fp):
                return False
            srcs[p] = open(fp, "rb").read()
        sheet_n = "xl/worksheets/sheet1.xml"
        rels_n = "xl/worksheets/_rels/sheet1.xml.rels"
        ct_n = "[Content_Types].xml"
        with zipfile.ZipFile(dst) as z:
            out = {i.filename: z.read(i.filename) for i in z.infolist()}
        if sheet_n not in out or rels_n not in out:
            return False
        rels = out[rels_n].decode("utf-8")
        used = set(_re.findall(r'Id="rId(\d+)"', rels))
        n = 1
        while str(n) in used:
            n += 1
        rid = "rId%d" % n
        sheet = out[sheet_n].decode("utf-8")
        if "<drawing " not in sheet:
            tag = '<drawing r:id="%s"/>' % rid
            # নিশ্চিত করি r: নেমস্পেস ঘোষিত আছে, নইলে মূল ট্যাগেই দিয়ে দিই
            root_end = sheet.find(">")
            root_tag = sheet[:root_end] if root_end > 0 else ""
            if "xmlns:r=" not in root_tag:
                if root_tag.endswith("/>"):
                    sheet = sheet.replace(root_tag,
                                          root_tag[:-2] + ' xmlns:r="%s"/>' % NS_R, 1)
                else:
                    sheet = sheet.replace(root_tag, root_tag + ' xmlns:r="%s"' % NS_R, 1)
            if "<legacyDrawing" in sheet:
                sheet = sheet.replace("<legacyDrawing", tag + "<legacyDrawing", 1)
            else:
                sheet = sheet.replace("</worksheet>", tag + "</worksheet>", 1)
            out[sheet_n] = sheet.encode("utf-8")
        if "drawings/drawing1.xml" not in rels:
            rels = rels.replace(
                "</Relationships>",
                '<Relationship Id="%s" Type="%s" Target="../drawings/drawing1.xml"/>'
                "</Relationships>" % (rid, DRAW_REL))
            out[rels_n] = rels.encode("utf-8")
        ct = out[ct_n].decode("utf-8")
        add = ""
        if "/xl/drawings/drawing1.xml" not in ct:
            add += ('<Override PartName="/xl/drawings/drawing1.xml" '
                    'ContentType="%s"/>' % DRAW_CT)
        for i in (1, 2, 3):
            pn = "/xl/ink/ink%d.xml" % i
            if pn not in ct:
                add += ('<Override PartName="%s" ContentType="application/inkml+xml"/>' % pn)
        if add:
            out[ct_n] = ct.replace("</Types>", add + "</Types>").encode("utf-8")
        for p, data in srcs.items():
            out[p] = data
        tmp = dst + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
            for name, data in out.items():
                zo.writestr(name, data)
        os.replace(tmp, dst)
        return True
    except Exception:
        try:
            if os.path.isfile(dst + ".tmp"):
                os.remove(dst + ".tmp")
        except OSError:
            pass
        return False


def parse_labor(path=None):
    """Read the labor sheet: one block per provider, 5 columns each.

    Row 2 carries the provider name (merged), row 4 the column headers,
    rows 5+ the workers. Duty history lives in the cell comments.
    """
    from openpyxl import load_workbook as _lwb
    fp = path or labor_ensure()
    wb = _lwb(fp, data_only=True)

    def _nm(v):
        return " ".join(str(v or "").split())

    providers, order = {}, []

    def _txt(v):
        if v is None:
            return ""
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        return _nm(v)

    for ws in wb.worksheets:
        # every "Name" header in row 4 starts a block
        for c in range(1, (ws.max_column or 0) + 1):
            if _nm(ws.cell(4, c).value).lower() != "name":
                continue
            prov = _nm(ws.cell(2, c).value) or "(প্রোভাইডারের নাম লেখা নেই)"
            if prov not in providers:
                providers[prov] = []
                order.append(prov)
            for r in range(5, (ws.max_row or 0) + 1):
                name = _nm(ws.cell(r, c).value)
                if not name:
                    continue
                site = _nm(ws.cell(r, c + 3).value)
                rate = ws.cell(r, c + 2).value
                try:
                    rate = float(rate) if rate not in (None, "") else None
                except (TypeError, ValueError):
                    rate = None
                # duty history is kept in the cell comments — প্রতিটি ঘরের
                # কমেন্ট আলাদা করে রাখা হয়, যাতে এডিট করলে জায়গা না বদলায়
                def _cmt(cc):
                    try:
                        cm = ws.cell(r, cc).comment
                    except Exception:
                        return ""
                    if cm and cm.text and cm.text.strip():
                        return " ".join(cm.text.split())
                    return ""

                c_name, c_date, c_site = _cmt(c), _cmt(c + 1), _cmt(c + 3)
                hist = []
                for t in (c_name, c_date, c_site):
                    if t and t not in hist:
                        hist.append(t)
                off = bool(site) and site.lower() in ("duty off", "end", "off", "duty end")
                providers[prov].append({
                    "name": name,
                    "legal": legal_name(name),
                    "start": _txt(ws.cell(r, c + 1).value),
                    "rate": rate,
                    "site": "" if off else site,
                    "off": off,
                    "history": hist,
                    "cmtName": c_name,
                    "cmtDate": c_date,
                    "cmtSite": c_site,
                    "col": c, "row": r,
                })
    wb.close()
    out = []
    for p in order:
        out.append({"provider": p, "workers": providers[p],
                    "onDuty": sum(1 for w in providers[p] if not w["off"]),
                    "off": sum(1 for w in providers[p] if w["off"])})
    return out


def norm_person(s):
    s = re.sub(r"\s*\(.*", "", str(s or ""))
    s = re.sub(r"^(md|mohammad)\s+", "", s.strip(), flags=re.I)
    return re.sub(r"[^a-z]", "", s.lower())


# LABOR_LEGAL-এর চাবি norm_person-এর আকারে, যাতে "Nennu Miah" আর
# "Nennu Miah " দুটোই মিলে যায়
LABOR_LEGAL_N = {norm_person(k): v for k, v in LABOR_LEGAL.items()}


def legal_name(name):
    return LABOR_LEGAL_N.get(norm_person(name), "")


ASSIGN_FILE = os.path.join(BASE, "labor_assign.json")
PHONE_FILE = os.path.join(BASE, "labor_phones.json")


def phones_load():
    try:
        with open(PHONE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def phones_save(d):
    bak = backup_file(PHONE_FILE) if os.path.isfile(PHONE_FILE) else None
    with open(PHONE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def wa_number(raw):
    """'+971 50 123 4567' / '00971501234567' -> '971501234567' (wa.me চাই)"""
    s = re.sub(r"[^\d]", "", str(raw or ""))
    if s.startswith("00"):
        s = s[2:]
    return s


RATE_FILE = os.path.join(BASE, "profit_rates.json")   # legacy site rates (fallback)
SRATE_FILE = os.path.join(BASE, "profit_srates.json")  # {normname: {name, rate}} — প্রতি লোকের সাইট রেট
DUTY_FILE = os.path.join(BASE, "profit_duty.json")     # {month: {normname: {name, splits:[{site,days,hours}]}}}
EXP_FILE = os.path.join(BASE, "profit_exp.json")       # [{month, label, amount}]
PAY_FILE = os.path.join(BASE, "profit_pay.json")       # {billMonth: {income: true, prov: {provider: true}}}


def rates_load():
    try:
        with open(RATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def rates_save(d):
    bak = backup_file(RATE_FILE) if os.path.isfile(RATE_FILE) else None
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def srates_load():
    try:
        with open(SRATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def srates_save(d):
    bak = backup_file(SRATE_FILE) if os.path.isfile(SRATE_FILE) else None
    with open(SRATE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def srate_of(name):
    try:
        hit = srates_load().get(norm_person(name)) or {}
        r = float(hit.get("rate", 0) or 0)
        return r if r > 0 else None
    except (TypeError, ValueError):
        return None


def duty_load():
    try:
        with open(DUTY_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def duty_save(d):
    bak = backup_file(DUTY_FILE) if os.path.isfile(DUTY_FILE) else None
    with open(DUTY_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def exp_load():
    try:
        with open(EXP_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def exp_save(lst):
    bak = backup_file(EXP_FILE) if os.path.isfile(EXP_FILE) else None
    with open(EXP_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=1)
    return bak


def pay_load():
    try:
        with open(PAY_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def pay_save(d):
    bak = backup_file(PAY_FILE) if os.path.isfile(PAY_FILE) else None
    with open(PAY_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def profit_total_files():
    """Total T ফাইলগুলো — নতুন আগে।"""
    out = []
    for d in (BASE, os.path.join(BASE, "output")):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.startswith("~") or not n.lower().endswith(".xlsx"):
                continue
            if "total" not in n.lower():
                continue
            p = os.path.join(d, n)
            rel = n if d == BASE else "output/" + n
            try:
                out.append({"file": rel, "mtime": os.path.getmtime(p)})
            except OSError:
                pass
    out.sort(key=lambda x: -x["mtime"])
    return out


def profit_hours(total_rel):
    """Total T file -> [{name, provider, hours, rate, total, adv, gas, site}]."""
    from generator import preview_total_sheet
    fp = os.path.normpath(os.path.join(BASE, total_rel))
    if not fp.startswith(os.path.normpath(BASE) + os.sep) or not os.path.isfile(fp):
        raise ValueError("ফাইল পাইনি")
    pv = preview_total_sheet(fp)

    def _num(v):
        try:
            return float(v) if v not in (None, "") else 0.0
        except (TypeError, ValueError):
            return 0.0

    workers, cur = [], ""
    for row in pv.get("grand", []):
        if row.get("t") == "ref":
            cur = str(row.get("text", ""))
        elif row.get("t") == "w":
            h, rt = _num(row.get("h")), _num(row.get("rate"))
            workers.append({
                "name": str(row.get("name", "")),
                "provider": cur,
                "hours": h,
                "rate": rt,
                # Total কলাম ফর্মুলা — data_only পড়ায় ক্যাশড ০ আসতে পারে,
                # তাই ঘণ্টা×রেট নিজে হিসাব করি (generator._build_worker-এর মতো)
                "total": round(h * rt, 2),
                "adv": _num(row.get("adv")),
                "gas": _num(row.get("gas")),
            })
    try:
        idx = labor_index()
    except Exception:
        idx = {}
    try:
        _srmap = srates_load()
    except Exception:
        _srmap = {}
    for w in workers:
        hit = idx.get(norm_person(w["name"])) or {}
        w["site"] = hit.get("site", "") or ""
        try:
            srh = _srmap.get(norm_person(w["name"])) or {}
            sr = float(srh.get("rate", 0) or 0)
            w["srate"] = sr if sr > 0 else None
        except (TypeError, ValueError):
            w["srate"] = None
    # day-level: A (absent) / S count from provider daily sheets
    try:
        cols = {}
        for si, sh in enumerate(pv.get("sheets", [])):
            for ci, nm in enumerate(sh.get("workers", [])):
                cols.setdefault(norm_person(nm), (si, ci))
        sheets = pv.get("sheets", [])
        for w in workers:
            a = s_ = 0
            hit = cols.get(norm_person(w["name"]))
            if hit:
                si, ci = hit
                for d in sheets[si].get("days", []):
                    v = d.get("v", []) or []
                    val = str(v[ci]).strip().upper() if ci < len(v) else ""
                    if val == "A":
                        a += 1
                    elif val == "S":
                        s_ += 1
            w["absent"] = a
            w["sick"] = s_
    except Exception:
        for w in workers:
            w.setdefault("absent", 0)
            w.setdefault("sick", 0)
    return workers


def labor_write(save, allow, label=""):
    """Backup -> save -> put the pictures/ink back -> verify -> roll back if odd."""
    fp = labor_ensure()
    bak = backup_file(fp)
    before = cellsnap(fp)
    wb = load_wb_for_write(fp)
    try:
        save(wb)
        wb.save(fp)
        wb.close()
    except Exception:
        try:
            wb.close()
        except Exception:
            pass
        raise
    if not restore_parts(fp):
        # ছবি/ইঙ্ক ফেরানো গেল না — নিরাপদে আগের অবস্থায় ফিরে যাই
        shutil.copy2(bak, fp)
        raise ValueError("ছবি/ইঙ্ক ফেরানো যায়নি — কোনো লেখা করা হয়নি")
    try:
        verify_written(fp)
        write_guard(fp, bak, before, allow)
    except Exception:
        shutil.copy2(bak, fp)
        restore_parts(fp)
        raise
    return bak


def load_wb_for_write(fp):
    from openpyxl import load_workbook as _lw
    return _lw(fp)


def labor_blocks(ws):
    """[(nc, provider, rows...)] - every 4-column block that has a 'Name' header."""
    out = []
    for c in range(1, (ws.max_column or 0) + 1):
        if _nmv(ws.cell(4, c).value).lower() == "name":
            out.append(c)
    return out


# --- নতুন প্রোভাইডারের ব্লক: ফাইলের নিজস্ব ফরম্যাট অনুসরণ করে ---------
LABOR_HEADERS = ("Name", "duty St Date", "Buy of Per Hour ",
                 "Duty now Running Comp or Site")
LABOR_W = 4          # একটি ব্লকে ৪টি কলাম (নাম, তারিখ, রেট, সাইট)
LABOR_GAP = 1        # দুই ব্লকের মাঝে ১টি ফাঁকা স্পেসার কলাম
LABOR_ROWS = 20      # যে সারি পর্যন্ত ফরম্যাট থাকে


def labor_free_block_col(ws, blocks):
    """শেষ ব্লকের পরে সম্পূর্ণ ফাঁকা ৪+১ কলামের জায়গা খোঁজে। না পেলে None।"""
    if not blocks:
        return 1
    mr = list(ws.merged_cells.ranges)
    c = max(blocks) + LABOR_W + LABOR_GAP
    limit = (ws.max_column or 0) + 60
    while c <= limit:
        busy = False
        for x in range(c, c + LABOR_W + LABOR_GAP):
            for m in mr:
                if not (m.max_col < x or m.min_col > x):
                    busy = True
                    break
            if busy:
                break
        if not busy:
            for r in range(1, (ws.max_row or 0) + 1):
                if any(ws.cell(r, x).value not in (None, "")
                       for x in range(c, c + LABOR_W + LABOR_GAP)):
                    busy = True
                    break
        if not busy:
            return c
        c += 1
    return None


def labor_style_block(ws, src, dst):
    """আগের ব্লকের ফরম্যাট হুবহু কপি করে নতুন ব্লকে বসায়।"""
    from copy import copy as _cp
    from openpyxl.utils import get_column_letter as _CL
    for r in list(range(1, 4)) + list(range(4, LABOR_ROWS + 1)):
        for i in range(LABOR_W):
            s = ws.cell(r, src + i)
            d = ws.cell(r, dst + i)
            d._style = _cp(s._style)
    for i in range(LABOR_W):
        cd = ws.column_dimensions[_CL(dst + i)]
        cd.width = ws.column_dimensions[_CL(src + i)].width or 29.45
    # দুই ব্লকের মাঝের ফাঁকা কলামটাও আগের মতো হবে (ব্লকের আগেরটা + পরেরটা)
    gs = ws.column_dimensions[_CL(src + LABOR_W)]
    if gs.width:
        ws.column_dimensions[_CL(dst + LABOR_W)].width = gs.width
    if dst - LABOR_GAP >= 1:
        pb = ws.column_dimensions[_CL(dst - LABOR_GAP)]
        if not pb.width or pb.width > 4:
            pb.width = gs.width or 2.3


def labor_make_block(ws, dst, provider):
    """নতুন প্রোভাইডারের ব্লক — টেমপ্লেট ব্লকের হুবহু ফরম্যাটে।"""
    from copy import copy as _cp
    blocks = labor_blocks(ws)
    src = blocks[0] if blocks else None
    if src is not None and src != dst:
        labor_style_block(ws, src, dst)
    # ব্যানার: হলুদ, মার্জড, মাঝখানি — টেমপ্লেট থেকে এসেছে
    ws.cell(2, dst).value = provider
    try:
        ws.merge_cells(start_row=2, start_column=dst,
                       end_row=3, end_column=dst + LABOR_W - 1)
    except Exception:
        pass
    # হেডার চারটি
    for i, h in enumerate(LABOR_HEADERS):
        ws.cell(4, dst + i).value = h
    return dst


def _nmv(v):
    return " ".join(str(v or "").split())


def _as_date(v):
    """'2026-10-16' বা '16/10/2026' -> আসল তারিখ; না পারলে লেখাটাই ফেরত।"""
    s = str(v or "").strip()
    if not s:
        return ""
    from datetime import datetime as _dt
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%y", "%Y/%m/%d",
              "%d.%m.%Y", "%d-%b-%Y", "%m/%d/%Y"):
        try:
            return _dt.strptime(s, f)
        except ValueError:
            continue
    return s


def _as_num(v):
    s = str(v or "").strip()
    if not s:
        return ""
    try:
        f = float(s)
    except ValueError:
        return s
    return int(f) if f == int(f) else f


def assign_load():
    try:
        with open(ASSIGN_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def assign_save(d):
    bak = backup_file(ASSIGN_FILE) if os.path.isfile(ASSIGN_FILE) else None
    with open(ASSIGN_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


PROVIDER_CONFIG_FILE = os.path.join(BASE, "provider_config.json")


def provider_config_load():
    try:
        with open(PROVIDER_CONFIG_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def provider_config_save(d):
    bak = backup_file(PROVIDER_CONFIG_FILE) if os.path.isfile(PROVIDER_CONFIG_FILE) else None
    with open(PROVIDER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return bak


def labor_index():
    """name -> {provider, ...worker record}, honouring the hand-made matches."""
    idx = {}
    for blk in parse_labor():
        for w in blk["workers"]:
            idx.setdefault(norm_person(w["name"]), dict(w, provider=blk["provider"]))
    out = {}
    for alias, real in LABOR_MATCH.items():
        hit = idx.get(norm_person(real))
        if hit:
            out[norm_person(alias)] = hit
    for k, v in idx.items():
        out.setdefault(k, v)
    # manual picks made from the UI always win
    for person, prov in assign_load().items():
        k = norm_person(person)
        if not k:
            continue
        hit = idx.get(norm_person(prov))
        if hit:
            out[k] = dict(hit, provider=prov)
        else:
            out[k] = {"name": person, "provider": prov, "site": "", "start": "",
                      "rate": None, "off": False, "history": []}
    return out


# ---------------------------------------------------------------- safety net
# Rule of the house: the bot READS the user's own files, but anything it
# WRITES inside the company tree goes to a file whose name carries "বট".
# Every write is backed up first and verified afterwards.
BOT_TAG = "বট"


def in_company(path):
    """True if path sits inside the company data root (the user's own files)."""
    try:
        p = os.path.normcase(os.path.abspath(path))
        r = os.path.normcase(os.path.abspath(DRIVE_DIR))
        return p == r or p.startswith(r + os.sep)
    except (OSError, ValueError):
        return False


def is_bot_file(path):
    return BOT_TAG in os.path.basename(path)


def bot_name(name):
    """Give a file the বট tag if it doesn't have one yet."""
    base, ext = os.path.splitext(name)
    if BOT_TAG in base:
        return name
    return "{} {}{}".format(base, BOT_TAG, ext)


def verify_written(path):
    """Confirm what we just wrote is a real, openable file."""
    if not os.path.isfile(path):
        raise ValueError("লেখা ফাইল পাওয়া যায়নি")
    if os.path.getsize(path) == 0:
        raise ValueError("লেখা ফাইল খালি হয়ে গেছে")
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook as _lv
        w = _lv(path, read_only=True)
        try:
            _ = w.sheetnames
        finally:
            w.close()
    return True


def roll_back(path, bak, existed):
    """Undo a bad write: restore the backup, or drop the new file."""
    try:
        if existed and bak and os.path.isfile(bak):
            shutil.copy2(bak, path)
        elif not existed and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def safe_copy_out(src, dst):
    """Copy a produced file to a destination folder without ever losing data.

    Inside the company tree the name is tagged with বট so the user's own
    files stay untouched. An existing destination is backed up, the copy is
    verified, and anything unexpected is rolled back.
    """
    folder = os.path.dirname(dst)
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(dst)
    tagged = False
    if in_company(dst) and not is_bot_file(dst):
        name = bot_name(name)
        tagged = name != os.path.basename(dst)
        dst = os.path.join(folder, name)
    existed = os.path.isfile(dst)
    # একই ফাইলের উপরে লেখা যায় না (WinError 32) — সেক্ষেত্রে " -কপি" নামে নতুন ফাইলে সেভ
    try:
        same = os.path.isfile(src) and os.path.isfile(dst) and os.path.samefile(src, dst)
    except OSError:
        same = False
    if same:
        stem, ext = os.path.splitext(name)
        cand, i = stem + " -কপি" + ext, 2
        while os.path.exists(os.path.join(folder, cand)):
            cand = "{0} -কপি {1}{2}".format(stem, i, ext)
            i += 1
        name = cand
        dst = os.path.join(folder, name)
        tagged = True
        existed = False
    bak = backup_file(dst) if existed else None
    shutil.copy2(src, dst)
    try:
        verify_written(dst)
    except Exception:
        roll_back(dst, bak, existed)
        raise
    return dst, bak, tagged
DRIVE_MAX_BYTES = 100 * 1024 * 1024
BLOCKED_EXT = {".exe", ".bat", ".cmd", ".msi", ".ps1", ".vbs", ".js", ".jar", ".com", ".scr"}
RCLONE = os.path.join(BASE, "drivers", "rclone.exe")
RCLONE_CONF = os.path.join(BASE, "rclone.conf")
RC_REMOTE = "onedrive:"


def rc_run(*args, timeout=120):
    """Run rclone with args; returns stdout text. Raises on failure."""
    import subprocess as _sp
    if not os.path.isfile(RCLONE):
        raise FileNotFoundError("rclone.exe নেই")
    cmd = [RCLONE, "--config", RCLONE_CONF, "--timeout", "30s", "--contimeout", "20s", "--retries", "1"] + list(args)
    p = _sp.run(cmd, stdin=_sp.DEVNULL, capture_output=True, timeout=timeout)
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace").strip()[:200]
        raise RuntimeError(err or "rclone failed")
    return (p.stdout or b"").decode("utf-8", "replace")


def rc_exists(remote):
    """True if a OneDrive path exists. Never raises - used for safety checks."""
    import subprocess as _sp
    if not os.path.isfile(RCLONE):
        return False
    cmd = [RCLONE, "--config", RCLONE_CONF, "--timeout", "20s", "--contimeout", "15s",
           "--retries", "1", "lsjson", "--files-only", "--max-depth", "1", remote]
    try:
        p = _sp.run(cmd, stdin=_sp.DEVNULL, capture_output=True, timeout=45)
        if p.returncode != 0:
            return False
        return bool((p.stdout or b"").decode("utf-8", "replace").strip())
    except (OSError, _sp.TimeoutExpired):
        return False


def rc_path(rel):
    """Sanitize OneDrive-relative path; raises ValueError on escape."""
    rel = (rel or "").replace("\\", "/").strip().strip("/")
    if not rel:
        return ""
    parts = []
    for seg in rel.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("invalid path")
        parts.append(seg)
    return "/".join(parts)
OCR_DIR = os.path.join(BASE, "ocr_uploads")
TRASH_DIR = os.path.join(BASE, "drive_trash")
TRASH_MAP = os.path.join(TRASH_DIR, "trash.json")
TRASH_DAYS = 30


def trash_purge():
    """Permanently remove trash items older than TRASH_DAYS. Returns count."""
    import time as _tm
    cutoff = _tm.time() - TRASH_DAYS * 86400
    m = trash_load()
    changed, n_rm = False, 0
    for tn in list(m.keys()):
        p = os.path.join(TRASH_DIR, tn)
        try:
            if not os.path.exists(p):
                del m[tn]
                changed = True
                continue
            if os.path.getmtime(p) < cutoff:
                if os.path.isfile(p):
                    os.remove(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p)
                del m[tn]
                changed = True
                n_rm += 1
        except OSError:
            pass
    if changed:
        trash_save(m)
    return n_rm


def trash_load():
    try:
        with open(TRASH_MAP, "r", encoding="utf-8") as f:
            m = json.load(f)
            return m if isinstance(m, dict) else {}
    except Exception:
        return {}


def trash_save(m):
    try:
        os.makedirs(TRASH_DIR, exist_ok=True)
        with open(TRASH_MAP, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False)
    except Exception:
        pass


def drive_path(rel):
    """Resolve a drive-relative path; raises ValueError on escape attempts."""
    rel = (rel or "").replace("/", os.sep).strip().strip(os.sep)
    base = os.path.normpath(DRIVE_DIR)
    p = os.path.normpath(os.path.join(base, rel)) if rel else base
    if p != base and not p.startswith(base + os.sep):
        raise ValueError("invalid path")
    return p
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(TRASH_DIR, exist_ok=True)
os.makedirs(CUSTOM_DIR, exist_ok=True)
os.makedirs(OCR_DIR, exist_ok=True)

USERS_FILE = os.path.join(BASE, ".users")
SESSION_TTL = 12 * 3600
SESSIONS = {}


def users_load():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            u = d.get("users")
            return u if isinstance(u, dict) else {}
    except Exception:
        return {}


def users_save(u):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": u}, f)


def lock_on():
    return bool(users_load())


def user_check(uid, password):
    try:
        u = users_load().get(str(uid or "").strip().lower())
        if not u:
            return False
        got = hashlib.sha256((u.get("salt", "") + str(password)).encode("utf-8")).hexdigest()
        import hmac as _hm
        return _hm.compare_digest(got, u.get("hash", ""))
    except Exception:
        return False


def user_set(uid, password, actor=None):
    uid = str(uid or "").strip().lower()
    password = str(password or "")
    if not re.fullmatch(r"[a-z0-9_.@\-]{3,64}", uid):
        raise ValueError("ID: ৩–৬৪ অক্ষর (a-z, 0-9, _, ., @, -)")
    if not (4 <= len(password) <= 64):
        raise ValueError("পাসওয়ার্ড ৪–৬৪ অক্ষরের হতে হবে")
    users = users_load()
    existing = users.get(uid)
    if existing and existing.get("permanent"):
        raise ValueError("স্থায়ী ID বদলানো যাবে না")
    if existing and actor != uid:
        raise ValueError("এই ID already আছে")
    if users and actor is None:
        raise ValueError("locked")
    salt = secrets.token_hex(16)
    users[uid] = {"salt": salt,
                  "hash": hashlib.sha256((salt + password).encode("utf-8")).hexdigest()}
    users_save(users)
    return uid


def session_token(headers):
    try:
        ck = headers.get("Cookie", "") or ""
        m = re.search(r"atk_session=([0-9a-f]{48})", ck)
        if not m:
            return None
        tok = m.group(1)
        s = SESSIONS.get(tok)
        if not s:
            return None
        if s.get("exp", 0) < time.time():
            SESSIONS.pop(tok, None)
            return None
        return s.get("user")
    except Exception:
        return None


XL_MAX_ROWS = 200
XL_MAX_COLS = 52  # A..AZ


def backup_file(path):
    """Timestamped backup BEFORE any work. Returns backup filename."""
    from datetime import datetime
    base = os.path.basename(path)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"{ts}_{base}"
    shutil.copy2(path, os.path.join(BACKUP_DIR, name))
    try:  # keep last 60 backups
        files = sorted(os.listdir(BACKUP_DIR))
        for old in files[:-60]:
            os.remove(os.path.join(BACKUP_DIR, old))
    except OSError:
        pass
    return name


def cellsnap(path):
    """{(row, col): "text value"} of every non-empty cell - used as a safety net."""
    from openpyxl import load_workbook as _lg
    w = _lg(path, data_only=True)
    out = {}
    try:
        for s in w.worksheets:
            for row in s.iter_rows():
                for c in row:
                    if c.value is None:
                        continue
                    v = c.value
                    if isinstance(v, float):
                        v = round(v, 2)
                    out[(c.row, c.column)] = str(v).strip()
    finally:
        w.close()
    return out


def _same_cell(a, b):
    if a == b:
        return True
    try:
        return abs(float(str(a).replace(",", "")) - float(str(b).replace(",", ""))) < 0.005
    except (TypeError, ValueError):
        return False


def commentsnap(path):
    """{(row, col): "text"} প্রতিটি কমেন্টের — ডিউটির ইতিহাস এখানেই থাকে।"""
    from openpyxl import load_workbook as _lgc
    w = _lgc(path)
    out = {}
    try:
        for s in w.worksheets:
            for row in s.iter_rows():
                for c in row:
                    try:
                        cm = c.comment
                    except Exception:
                        cm = None
                    if cm and str(cm.text or "").strip():
                        out[(c.row, c.column)] = " ".join(str(cm.text).split())
    except Exception:
        return {}
    finally:
        w.close()
    return out


def comment_guard(fp, bak, before, allow):
    """লেখার পরে কোনো কমেন্ট হারিয়ে গেলে ফাইল ব্যাকআপে ফেরায়।

    cellsnap শুধু ঘরের লেখা দেখে, কমেন্ট দেখে না — তাই লাল ত্রিভূজ
    চুপচাপ মুছে যেতে পারত। এই নিরাপনেটা সেটাই ঠেকায়।
    """
    after = commentsnap(fp)
    lost = [k for k, v in before.items()
            if k not in allow and after.get(k) != v]
    if lost:
        shutil.copy2(bak, fp)
        from openpyxl.utils import get_column_letter as _CL
        raise ValueError(
            "ডিউটির ইতিহাস (কমেন্ট) মুছে যাচ্ছিল — ফাইল ব্যাকআপ থেকে ফেরানো হয়েছে। "
            "যে ঘরগুলো বাঁচানো হয়েছে: %s"
            % ", ".join("%s%d" % (_CL(c), r) for r, c in sorted(lost)[:6]))
    return True


def write_guard(fp, bak, before, allow):
    """Roll the file back if a write touched anything it was not allowed to.

    allow = set of (row, col) this write is permitted to create/clear.
    The Advance sheet keeps 12 people side by side, so one careless write can
    silently wipe a neighbour's entry. This makes that impossible to commit.
    """
    after = cellsnap(fp)
    bad = []
    for k, v in before.items():
        if k in allow:
            continue
        if k not in after or not _same_cell(v, after[k]):
            bad.append(k)
    for k in after:
        if k not in before and k not in allow:
            bad.append(k)
    if bad:
        shutil.copy2(bak, fp)
        raise ValueError(
            "অন্য কারো লেখা বদলে গিয়েছিল — ফাইল ব্যাকআপ থেকে ফেরানো হয়েছে (%s)"
            % os.path.basename(bak))
    return True


def resolve_file(name):
    # Exact basename match first; fallback to whitespace-normalized match
    # (HTML <option> without value collapses double spaces, so be tolerant).
    name = os.path.basename(name or "")
    if not name:
        raise FileNotFoundError("empty filename")
    # ইনপুট ফোল্ডার আগে — এটাই ব্যবহারকারীর আসল ফাইল (Data sheet / Total Master sheet)
    if os.path.isdir(INPUT_DIR):
        p = os.path.join(INPUT_DIR, name)
        if os.path.isfile(p):
            return p
    p = os.path.join(BASE, name)
    if os.path.isfile(p):
        return p
    norm = re.sub(r"\s+", " ", name).strip().lower()
    for d in (INPUT_DIR, BASE):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith(".xlsx") and re.sub(r"\s+", " ", f).strip().lower() == norm:
                return os.path.join(d, f)
    raise FileNotFoundError(name)


def _dsheet_snapshot(path):
    """{normname: {hours, rate, srate, adv, gas, days}} for a data sheet — best effort."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    try:
        from generator import locate_data_table, _num_or_none, to_hours, norm_person
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        m = locate_data_table(ws)
        if not m:
            wb.close()
            return out
        for r in range(m["first_row"], ws.max_row + 1):
            nm = ws.cell(r, m["name"]).value if m["name"] else None
            if nm is None or not str(nm).strip():
                continue
            days = 0.0
            for d in range(1, 32):
                if d in m["days"]:
                    try:
                        days += to_hours(ws.cell(r, m["days"][d]).value)[0]
                    except Exception:
                        pass
            g = lambda k: _num_or_none(ws.cell(r, m[k]).value if m.get(k) else None)
            out[norm_person(str(nm).strip())] = {
                "name": str(nm).strip(),
                "hours": round(days, 2),
                "rate": g("rate"), "srate": g("site_rate"),
                "adv": g("advance"), "gas": g("gas"),
            }
        wb.close()
    except Exception:
        return {}
    return out


def _upload_risk_report(new_path, old_path):
    """What would be LOST if we overwrite old_path with new_path. Empty = safe."""
    new = _dsheet_snapshot(new_path)
    old = _dsheet_snapshot(old_path)
    if not new or not old:
        return {"safe": True, "lost": [], "note": "তুলনা করা গেল না"}
    lost = []
    for k, o in old.items():
        n = new.get(k)
        if not n:
            lost.append({"name": o["name"], "what": "লোকটা নেই", "was": "পুরো লাইন"})
            continue
        parts = []
        if (o["hours"] or 0) - (n["hours"] or 0) > 0.5:
            parts.append("ঘণ্টা %g → %g" % (o["hours"] or 0, n["hours"] or 0))
        if (o["adv"] or 0) - (n["adv"] or 0) > 0.5:
            parts.append("এডভাঞ্স %g → %g" % (o["adv"] or 0, n["adv"] or 0))
        if (o["gas"] or 0) - (n["gas"] or 0) > 0.5:
            parts.append("গ্যাস %g → %g" % (o["gas"] or 0, n["gas"] or 0))
        # a rate that simply drops to blank means the row is stale, not that
        # the user meant to clear it -> that one is worth shouting about
        if (o["rate"] or 0) > 0 and not (n["rate"] or 0):
            parts.append("রেট %g → ফাঁকা" % (o["rate"] or 0))
        if (o["srate"] or 0) > 0 and not (n["srate"] or 0):
            parts.append("সাইট রেট %g → ফাঁকা" % (o["srate"] or 0))
        if parts:
            lost.append({"name": o["name"], "what": ", ".join(parts), "was": ""})
    return {"safe": not lost, "lost": lost,
            "old_n": len(old), "new_n": len(new)}



def _repair_site_rate_column(path):
    """The Site Rate column is newer than the rest of the sheet, so an older
    copy can arrive without its borders/yellow header. Re-borrow the look from
    the neighbouring Rate column so it never shows up as a blank gap."""
    try:
        from copy import copy as _cp
        from openpyxl import load_workbook
        from generator import locate_data_table
        wb = load_workbook(path)
        ws = wb.active
        m = locate_data_table(ws)
        if not (m and m.get("rate") and m.get("site_rate")):
            wb.close()
            return False
        dc, tc = m["rate"], m["site_rate"]
        changed = False
        for r in range(2, ws.max_row + 1):
            src, dst = ws.cell(r, dc), ws.cell(r, tc)
            if src is None or dst is None:
                continue
            sb, db = src.border, dst.border
            missing = any(not (getattr(db, k).style if getattr(db, k, None) else None)
                          for k in ("left", "right", "top", "bottom"))
            if missing and any(getattr(sb, k).style for k in ("left", "right", "top", "bottom")):
                v = dst.value
                dst.border = _cp(sb)
                dst.font = _cp(src.font)
                dst.alignment = _cp(src.alignment)
                dst.number_format = src.number_format
                dst.value = v
                changed = True
        if changed:
            hb, db = ws.cell(2, dc).border, ws.cell(2, tc).border
            if not (db.left and db.left.style) and (hb.left and hb.left.style):
                v = ws.cell(2, tc).value
                ws.cell(2, tc).border = _cp(hb)
                ws.cell(2, tc).font = _cp(ws.cell(2, dc).font)
                ws.cell(2, tc).alignment = _cp(ws.cell(2, dc).alignment)
                ws.cell(2, tc).value = v
            from openpyxl.utils import get_column_letter as _gcl
            if not ws.column_dimensions[_gcl(tc)].width:
                ws.column_dimensions[_gcl(tc)].width = \
                    ws.column_dimensions[_gcl(dc)].width or 11.7
            wb.save(path)
        wb.close()
        return changed
    except Exception:
        return False


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def xl_col_letters(n):
    s = ""
    while n > 0:
        n, m = divmod(n - 1, 26)
        s = chr(65 + m) + s
    return s


def xl_parse_cell(cell, raw):
    """Client cell {v, f:{b,i,u,al,alv,sz,bg,fg,fn,bd,wrap,num}} -> (value, font, fill, alignment)."""
    from openpyxl.styles import PatternFill as _PF, Color as _C, Font as _F, Alignment as _A, Border as _B, Side as _S
    v = raw.get("v", "")
    if v is None:
        v = ""
    if isinstance(v, str):
        s = v.strip()
        # real Excel formulas stay formulas (Excel evaluates on open)
        if s.startswith("=") and len(s) > 1:
            v = s
        # leading-zero codes / phone numbers stay text
        elif re.fullmatch(r"0\d+", s):
            v = s
        elif re.fullmatch(r"-?\d+(\.\d+)?", s):
            try:
                v = float(s) if "." in s else int(s)
            except Exception:
                v = s
    f = raw.get("f") or {}
    _fn = str(f.get("fn") or "").strip()[:40] or "Calibri"
    font = _F(name=_fn, bold=bool(f.get("b")), italic=bool(f.get("i")),
              underline="single" if f.get("u") else None,
              sz=float(f["sz"]) if f.get("sz") else 11)
    if f.get("fg") and re.fullmatch(r"[0-9A-Fa-f]{6}", str(f["fg"])):
        font.color = _C(rgb="FF" + str(f["fg"]).upper())
    fill = _PF()
    if f.get("bg") and re.fullmatch(r"[0-9A-Fa-f]{6}", str(f["bg"])):
        fill = _PF("solid", fgColor="FF" + str(f["bg"]).upper())
    align = _A()
    if f.get("al") in ("left", "center", "right"):
        align.horizontal = f["al"]
    if f.get("alv") in ("top", "center", "bottom"):
        align.vertical = f["alv"]
    if f.get("wrap"):
        align.wrap_text = True
    try:
        thin = _S(style="thin", color=_C(rgb="FF000000"))
        bd = _B(left=thin, right=thin, top=thin, bottom=thin) if f.get("bd") else _B()
    except Exception:
        bd = _B()
    nf = str(f.get("num") or "General")[:40]
    return v, font, fill, align, bd, nf


def xl_read_cell(cell):
    """openpyxl cell -> client {v, f} (sparse: omit empties)."""
    v = cell.value
    if v is None or (isinstance(v, str) and v == ""):
        has_fmt = False
        try:
            has_fmt = bool((cell.font and (cell.font.bold or cell.font.italic)) or
                           (cell.fill and cell.fill.patternType == "solid"))
        except Exception:
            pass
        if not has_fmt:
            return None
        v = ""
    out = {"v": v if not hasattr(v, "strftime") else v}
    if hasattr(v, "strftime"):
        out["v"] = {"__date__": v.isoformat()}
    try:
        from generator import cell_format as _cf
        f = _cf(cell)
        if f:
            out["f"] = f
    except Exception:
        pass
    return out


from generator import (parse_data_sheet, generate_total_sheet, get_data_grid,
                         save_data_sheet, preview_total_sheet, analyze_data_sheet)


def parse_multipart(body, boundary):
    # Minimal multipart/form-data parser -> {field: (filename, bytes)}.
    out = {}
    for part in body.split(b"--" + boundary):
        if not part.strip() or part.strip() in (b"--", b"--\r\n"):
            continue
        head, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        htxt = head.decode("utf-8", "replace")
        mn = re.search(r'name="([^"]+)"', htxt)
        fn = re.search(r'filename="([^"]*)"', htxt)
        if mn:
            out[mn.group(1)] = ((fn.group(1) if fn else None), content)
    return out


# ============================================================================
# EXTENSION LOADER — extensions/ ফোল্ডারের নতুন .py ফাইল অটো লোড হয়।
# কোর ইঞ্জিন ছোঁয়া ছাড়া নতুন ফিচার যোগ করতে extensions/ এ ফাইল রাখুন।
# প্রতিটি ফাইলে GET_ROUTES / POST_ROUTES dict বানান:
#   GET_ROUTES  = {"/api/ext/my-get":  f}
#   POST_ROUTES = {"/api/ext/my-post": f}
# GET handler:  f(handler, path, query_dict)  -> handler._json({...})
# POST handler: f(handler, path, body_dict)   -> handler._json({...})
# ============================================================================
_EXT_GET, _EXT_POST = {}, {}

def load_extensions():
    """extensions/ ফোল্ডারের সব .py ফাইল লোড করে, route map বানায়।"""
    global _EXT_GET, _EXT_POST
    ext_dir = os.path.join(BASE, "extensions")
    if not os.path.isdir(ext_dir):
        return
    import importlib.util as _ilu
    for fn in sorted(os.listdir(ext_dir)):
        if not fn.endswith(".py") or fn.startswith(("_", ".")):
            continue
        fp = os.path.join(ext_dir, fn)
        name = "atk_ext_" + fn[:-3]
        try:
            spec = _ilu.spec_from_file_location(name, fp)
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            gr = getattr(mod, "GET_ROUTES", None)
            pr = getattr(mod, "POST_ROUTES", None)
            if isinstance(gr, dict):
                _EXT_GET.update(gr)
            if isinstance(pr, dict):
                _EXT_POST.update(pr)
            print("[ext] loaded:", fn)
        except Exception as _e:
            print("[ext] ERROR in", fn, ":", _e)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        try:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def _login_page(self):
        try:
            with open(os.path.join(BASE, "login.html"), "rb") as f:
                body = f.read()
        except OSError:
            body = b"Locked - set PIN"
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def _session_cookie(self, tok, age):
        data = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie",
                         f"atk_session={tok}; HttpOnly; Path=/; SameSite=Lax; Max-Age={age}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        if p.path == "/api/lock/status":
            me = session_token(self.headers)
            perm = False
            try:
                perm = bool(me and users_load().get(me, {}).get("permanent"))
            except Exception:
                pass
            self._json({"ok": True, "has_users": lock_on(),
                        "authed": me is not None, "user": me, "permanent": perm})
            return
        if p.path in ("/", "/index.html", "/workspace", "/workspace.js", "/unified_add.js", "/profit.js", "/dash.js"):
            if lock_on() and session_token(self.headers) is None:
                self._login_page()
                return
        elif p.path.startswith("/api/") or p.path == "/download":
            if lock_on() and session_token(self.headers) is None:
                self._json({"ok": False, "error": "locked"}, 401)
                return
        if p.path in ("/", "/index.html"):
            with open(os.path.join(BASE, "dashboard.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
            return
        if p.path == "/workspace":
            with open(os.path.join(BASE, "workspace.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path in ("/workspace.js", "/unified_add.js", "/profit.js", "/dash.js"):
            fn = os.path.join(BASE, os.path.basename(p.path))
            try:
                with open(fn, "rb") as f:
                    body = f.read()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/ws/employees":
            try:
                base = os.path.join(DRIVE_DIR, "separet all doc")
                if not os.path.isdir(base):
                    raise FileNotFoundError("separet all doc ফোল্ডার নেই")
                out = []
                with os.scandir(base) as it:
                    for e in it:
                        if not e.is_dir(follow_symlinks=False):
                            continue
                        nfiles, total = 0, 0
                        for _r, _ds, _fs in os.walk(e.path):
                            for _f in _fs:
                                nfiles += 1
                                try:
                                    total += os.path.getsize(os.path.join(_r, _f))
                                except OSError:
                                    pass
                        out.append({"name": e.name, "files": nfiles, "size": total})
                out.sort(key=lambda x: x["name"].lower())
                self._json({"ok": True, "employees": out})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/ws/employee-files":
            rel = (q.get("name") or [""])[0]
            try:
                base = os.path.join(DRIVE_DIR, "separet all doc")
                dp = os.path.normpath(os.path.join(base, rel))
                if not dp.startswith(os.path.normpath(base) + os.sep) or not os.path.isdir(dp):
                    raise ValueError("invalid name")
                files = []
                for _r, _ds, _fs in os.walk(dp):
                    for _f in _fs:
                        fp = os.path.join(_r, _f)
                        rp = os.path.relpath(fp, dp)
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            sz = 0
                        files.append({"name": rp.replace(os.sep, "/"), "size": sz})
                files.sort(key=lambda x: x["name"].lower())
                self._json({"ok": True, "name": rel, "files": files})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/ws/advance":
            try:
                from openpyxl import load_workbook as _lw2
                fp = advance_ensure()
                if not os.path.isfile(fp):
                    raise FileNotFoundError(ADV_BOT + " নেই")
                ws = _lw2(fp, data_only=True)["Sheet1"]
                people, order = {}, []

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

                def _fnum(v):
                    m = re.search(r"[\d,]+(\.\d+)?", str(v or ""))
                    return _num(m.group(0)) if m else 0

                def _cleared(st):
                    s = st.lower()
                    return ("paid" in s) or ("clear" in s)

                def _istotal(name):
                    s = name.lower()
                    return s.startswith("total") or s.startswith("grand balance")

                # header row 4: every "Name" cell starts a 5-col block
                blocks = []
                for c in range(1, (ws.max_column or 0) + 1):
                    if _nm(ws.cell(4, c).value).lower() == "name":
                        blocks.append((c, c + 1, c + 2, c + 3, c + 4))
                if not blocks:
                    blocks = [(6, 7, 8, 9, 10)]

                for _nc, _ac, _dc, _sc, _rc in blocks:
                    cur, last = None, None
                    for r in range(5, (ws.max_row or 0) + 1):
                        name = _nm(ws.cell(r, _nc).value)
                        if not name:
                            continue
                        if _istotal(name):
                            if last:
                                people[last].setdefault("file_totals", []).append(
                                    _fnum(ws.cell(r, _ac).value or name))
                                people[last]["file_total"] = people[last]["file_totals"][-1]
                            cur = None
                            continue
                        key = _key(name)
                        if not key:
                            continue
                        if key not in people:
                            people[key] = {"name": re.sub(r"\s*\(.*", "", name).strip(), "entries": [], "paid": 0,
                                           "balance": 0, "total": 0, "file_total": None}
                            order.append(key)
                        cur = people[key]
                        last = key
                        amt = _num(ws.cell(r, _ac).value)
                        dt = ws.cell(r, _dc).value
                        if hasattr(dt, "strftime"):
                            dt = dt.date().isoformat()
                        else:
                            dt = str(dt or "").strip()
                        st = _nm(ws.cell(r, _sc).value)
                        reason = _nm(ws.cell(r, _rc).value)
                        cur["entries"].append({"amount": amt, "date": dt,
                                               "status": st, "reason": reason})
                        cur["total"] += amt
                        if _cleared(st):
                            cur["paid"] += amt
                        else:
                            cur["balance"] += amt
                blocks = [people[k] for k in order]
                # কে কোন প্রোভাইডারের লোক, কোথায় ডিউটিতে
                try:
                    lidx = labor_index()
                except Exception:
                    lidx = {}
                _non_worker = {norm_person(x) for x in LABOR_NON_WORKER}
                for b in blocks:
                    k = norm_person(b["name"])
                    hit = lidx.get(k)
                    if hit:
                        b["provider"] = hit.get("provider")
                        b["labor"] = hit.get("name")
                        b["site"] = hit.get("site") or ""
                        b["dutyStart"] = hit.get("start") or ""
                        b["rate"] = hit.get("rate")
                        b["dutyOff"] = bool(hit.get("off"))
                    elif k in _non_worker:
                        b["provider"] = "প্রোভাইডার/রেফারেন্স"
                        b["labor"] = b["name"]
                    else:
                        b["provider"] = None
                        b["labor"] = b["name"]
                grand = sum(b["total"] for b in blocks)
                self._json({"ok": True, "people": blocks, "grand": grand,
                            "count": len(blocks)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/ws/phones":
            try:
                self._json({"ok": True, "phones": phones_load()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/ws/profit":
            try:
                files = profit_total_files()
                want = (q.get("file") or [""])[0].strip()
                if not want and files:
                    want = files[0]["file"]
                workers = profit_hours(want) if want else []
                self._json({"ok": True, "rates": rates_load(),
                            "srates": srates_load(),
                            "duty": duty_load(),
                            "expenses": exp_load(), "files": files,
                            "file": want, "workers": workers,
                            "pay": pay_load()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/ws/labor":
            try:
                blocks = parse_labor()
                self._json({"ok": True, "providers": blocks,
                            "file": os.path.basename(LABOR_FILE),
                            "total": sum(len(b["workers"]) for b in blocks)})
            except PermissionError:
                self._json({"ok": False, "locked": True,
                            "error": "এক্সেলে ফাইলটা খোলা আছে। এক্সেল বন্ধ করে "
                                     "আবার চেষ্টা করুন — বট তখনই লিখতে পারবে।"}, 423)
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/setup-status":
            try:
                self._json({"ok": True, **setup_status()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/cycle":
            try:
                import cycle as _cy
                # provider names must match ws8 exactly, so read them from
                # the same source the profit tab uses
                provs = []
                try:
                    _files = profit_total_files()
                    _want = _files[0]["file"] if _files else ""
                    for w in (profit_hours(_want) if _want else []):
                        pr = str(w.get("provider") or "").strip()
                        if pr and pr not in provs:
                            provs.append(pr)
                except Exception:
                    try:
                        for b in labor_index().values():
                            pr = (b.get("provider") or "").strip()
                            if pr and pr not in provs:
                                provs.append(pr)
                    except Exception:
                        pass
                pay = {}
                try:
                    with open(os.path.join(BASE, "profit_pay.json"), encoding="utf-8") as f:
                        pay = json.load(f)
                except Exception:
                    pass
                back = int((q.get("back") or ["3"])[0])
                fwd = int((q.get("fwd") or ["1"])[0])
                st = (q.get("start") or ["2026-09"])[0]
                self._json(_cy.cycle_state(providers=provs, pay=pay,
                                           start=st, months_back=back, months_fwd=fwd))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/api/memory":
            try:
                import botmem
                self._json({"ok": True, "memory": botmem.mem_load()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/advance-check":
            fname = (q.get("file") or [""])[0]
            try:
                import botmem
                people = botmem.advance_people(advance_ensure())
                res = botmem.advance_check(resolve_file(fname), people, LABOR_MATCH)
                tot = sum(r["diff"] for r in res["alerts"] if r["diff"] > 0)
                res["totalMissing"] = tot
                res["ok"] = True
                self._json(res)
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/files":
            # সাম্প্রতিকভাবে বদলানো ফাইল আগে — ড্রপডাউনে সবসময় সক্রিয় ফাইল উপরে থাকবে
            # ইনপুট ফোল্ডারের ফাইলগুলোই মূল — প্লাস বট-হোমের ফাইল, মডিফাই-টাইম অনুযায়ী সাজানো
            _src = INPUT_DIR if os.path.isdir(INPUT_DIR) else BASE
            _home = [f for f in os.listdir(BASE) if f.lower().endswith(".xlsx")]
            _inp = [f for f in os.listdir(_src) if f.lower().endswith(".xlsx")] if _src != BASE else []
            # বট নিজে যে ফাইল বানায় (AUTO / বট) সেগুলো ইনপুট নয় — ড্রপডাউনে দেখাবো না
            def _is_input(f):
                low = f.lower()
                return "auto" not in low and "বট" not in f and "(7)" not in f
            xlsx = sorted(set(_home) | set(_inp),
                           key=lambda f: os.path.getmtime(
                               os.path.join(_src, f) if f in _inp else os.path.join(BASE, f)),
                           reverse=True)
            xlsx = [f for f in xlsx if _is_input(f)]
            # Total T ফাইল ডাটা-ড্রপডাউনে যাবে না — শুধু Template/Output-এ (ড্রপডাউন পরিষ্কার রাখতে)
            data = [f for f in xlsx if "total" not in f.lower()]
            tmpl = [f for f in xlsx if "total" in f.lower()]
            # ইনপুট ফোল্ডারে মাস্টার থাকলে সেটাই আগে দেখাই (নতুন সিস্টেম)
            _inp_order = [f for f in _inp if _is_input(f)]
            tmpl.sort(key=lambda f: (0 if f in _inp_order else 1))
            outs = sorted(os.listdir(OUT_DIR))
            home = os.path.expanduser("~")
            places = {"Output folder": OUT_DIR,
                      "Desktop": os.path.join(home, "Desktop"),
                      "Documents": os.path.join(home, "Documents")}
            self._json({"data": data, "templates": tmpl or data, "all": xlsx,
                        "outputs": outs, "places": places})
            return
        if p.path == "/api/preview":
            fname = (q.get("file") or [""])[0]
            try:
                path = resolve_file(fname)
                a = analyze_data_sheet(path)
                self._json({"workers": a["workers"], "warnings": a["warnings"],
                            "meta": a["meta"]})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/api/data-grid":
            fname = (q.get("file") or [""])[0]
            try:
                self._json(get_data_grid(resolve_file(fname)))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/api/total-preview":
            fname = os.path.basename((q.get("file") or [""])[0])
            path = os.path.join(OUT_DIR, fname)
            try:
                self._json(preview_total_sheet(path))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/api/backups":
            try:
                items = []
                for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
                    fp = os.path.join(BACKUP_DIR, f)
                    if os.path.isfile(fp):
                        items.append({"name": f, "size": os.path.getsize(fp),
                                      "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(fp)))})
                self._json({"backups": items})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/download":
            fname = os.path.basename((q.get("file") or [""])[0])
            path = os.path.join(OUT_DIR, fname)
            if not os.path.isfile(path):
                self.send_error(404, "not found")
                return
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/xl/files":
            try:
                outs = sorted([f for f in os.listdir(CUSTOM_DIR) if f.lower().endswith(".xlsx")])
                self._json({"files": outs})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p.path == "/api/xl/open":
            from openpyxl import load_workbook as _lw
            fname = os.path.basename((q.get("file") or [""])[0])
            path = os.path.join(CUSTOM_DIR, fname)
            try:
                if not (fname and os.path.isfile(path)):
                    raise FileNotFoundError("not found: " + fname)
                wbin = _lw(path)
                sheets = []
                for sn in wbin.sheetnames:
                    wsin = wbin[sn]
                    cells = {}
                    maxR = min(wsin.max_row or 0, XL_MAX_ROWS)
                    maxC = min(wsin.max_column or 0, XL_MAX_COLS)
                    for r in range(1, maxR + 1):
                        for c in range(1, maxC + 1):
                            cell = wsin.cell(r, c)
                            got = xl_read_cell(cell)
                            if got is not None:
                                cells[f"{r},{c}"] = got
                    merges = []
                    try:
                        for mr in wsin.merged_cells.ranges:
                            r1 = max(1, mr.min_row)
                            c1 = max(1, mr.min_col)
                            r2 = min(mr.max_row, XL_MAX_ROWS)
                            c2 = min(mr.max_col, XL_MAX_COLS)
                            if r2 > r1 or c2 > c1:
                                merges.append([r1, c1, r2, c2])
                    except Exception:
                        pass
                    sheets.append({"name": sn, "cells": cells, "merges": merges,
                                   "maxR": maxR, "maxC": maxC})
                wbin.close()
                self._json({"ok": True, "sheets": sheets})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/months":
            try:
                import months as _months
                self._json({"ok": True, "root": _months.MONTHS_DIR,
                            "months": _months.list_months()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/data-download":
            fname = os.path.basename((q.get("file") or [""])[0])
            try:
                path = resolve_file(fname)
            except FileNotFoundError:
                self.send_error(404, "not found")
                return
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%s" % urllib.parse.quote(os.path.basename(path)))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/labor-download":
            try:
                path = labor_ensure()
                with open(path, "rb") as f:
                    body = f.read()
            except PermissionError:
                self._json({"ok": False, "locked": True,
                            "error": "এক্সেলে ফাইলটা খোলা আছে। এক্সেল বন্ধ করে "
                                     "তারপর চেষ্টা করুন।"}, 423)
                return
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''%s"
                             % urllib.parse.quote(os.path.basename(path)))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/xl/download":
            fname = os.path.basename((q.get("file") or [""])[0])
            path = os.path.join(CUSTOM_DIR, fname)
            if not (fname and os.path.isfile(path)):
                self.send_error(404, "not found")
                return
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == "/api/drive":
            rel = (q.get("path") or [""])[0]
            try:
                dp = drive_path(rel)
                if not os.path.isdir(dp):
                    raise FileNotFoundError("folder not found")
                folders, files = [], []
                with os.scandir(dp) as it:
                    for e in it:
                        try:
                            st = e.stat()
                        except OSError:
                            continue
                        if e.is_dir(follow_symlinks=False):
                            folders.append({"name": e.name, "mtime": st.st_mtime})
                        elif e.is_file(follow_symlinks=False):
                            files.append({"name": e.name, "size": st.st_size, "mtime": st.st_mtime})
                folders.sort(key=lambda x: x["name"].lower())
                files.sort(key=lambda x: x["name"].lower())
                total = 0
                for _r, _ds, _fs in os.walk(DRIVE_DIR):
                    for _f in _fs:
                        try:
                            total += os.path.getsize(os.path.join(_r, _f))
                        except OSError:
                            pass
                self._json({"ok": True, "path": rel, "folders": folders, "files": files,
                            "total_bytes": total})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/drive/trash":
            try:
                trash_purge()
                m = trash_load()
                items = []
                for tn, info in m.items():
                    tp = os.path.join(TRASH_DIR, tn)
                    if not os.path.exists(tp):
                        continue
                    try:
                        sz = 0
                        if os.path.isfile(tp):
                            sz = os.path.getsize(tp)
                        else:
                            for _r, _ds, _fs in os.walk(tp):
                                for _f in _fs:
                                    try:
                                        sz += os.path.getsize(os.path.join(_r, _f))
                                    except OSError:
                                        pass
                        items.append({"name": tn, "orig": info.get("orig", ""),
                                      "isdir": info.get("isdir", False),
                                      "time": info.get("time", ""), "size": sz})
                    except OSError:
                        pass
                items.sort(key=lambda x: x["time"], reverse=True)
                self._json({"ok": True, "items": items})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if p.path == "/api/drive/trash-file":
            tn = os.path.basename((q.get("name") or [""])[0])
            try:
                tp = os.path.join(TRASH_DIR, tn)
                if not tn or os.path.normpath(tp) != tp or not os.path.isfile(tp):
                    raise FileNotFoundError("not found")
                if not os.path.normpath(tp).startswith(os.path.normpath(TRASH_DIR) + os.sep):
                    raise ValueError("invalid")
                import mimetypes as _mt2
                ctype, _enc = _mt2.guess_type(tp)
                with open(tp, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(404, "not found")
            return
        if p.path == "/api/od/quota":
            try:
                out = rc_run("about", RC_REMOTE, "--json", timeout=120)
                q = json.loads(out or "{}")
                total = int(q.get("total") or 0)
                used = int(q.get("used") or 0)
                pct = round(100.0 * used / total, 1) if total > 0 else 0
                self._json({"ok": True, "used": used, "total": total, "pct": pct})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:160]}, 500)
            return
        if p.path == "/api/od/status":
            try:
                out = rc_run("lsjson", RC_REMOTE, "--max-depth", "1", timeout=90)
                json.loads(out or "[]")
                self._json({"ok": True, "connected": True})
            except Exception as e:
                self._json({"ok": True, "connected": False, "error": str(e)[:160]})
            return
        if p.path == "/api/od/list":
            rel = (q.get("path") or [""])[0]
            try:
                rp = rc_path(rel)
                out = rc_run("lsjson", RC_REMOTE + rp, timeout=120)
                items = json.loads(out or "[]")
                folders = [{"name": it["Name"], "mtime": it.get("ModTime", "")}
                           for it in items if it.get("IsDir")]
                files = [{"name": it["Name"], "size": it.get("Size", 0),
                          "mtime": it.get("ModTime", "")}
                         for it in items if not it.get("IsDir")]
                folders.sort(key=lambda x: x["name"].lower())
                files.sort(key=lambda x: x["name"].lower())
                self._json({"ok": True, "path": rp, "folders": folders, "files": files})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:200]}, 500)
            return
        if p.path == "/api/od/download":
            rel = (q.get("path") or [""])[0]
            try:
                rp = rc_path(rel)
                if not rp:
                    raise ValueError("invalid path")
                import subprocess as _sp, mimetypes as _mt3
                if not os.path.isfile(RCLONE):
                    raise FileNotFoundError("rclone.exe নেই")
                pr = _sp.run([RCLONE, "--config", RCLONE_CONF, "--timeout", "30s", "--contimeout", "20s", "--retries", "1", "cat", RC_REMOTE + rp], stdin=_sp.DEVNULL, capture_output=True, timeout=150)
                if pr.returncode != 0:
                    raise RuntimeError("download failed")
                body = pr.stdout or b""
                ctype, _e = _mt3.guess_type(rp)
                self.send_response(200)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                if not q.get("view"):
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(os.path.basename(rp))}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(404, "not found")
            return
        if p.path == "/api/drive/download":
            rel = (q.get("path") or [""])[0]
            try:
                dp = drive_path(rel)
                if not os.path.isfile(dp):
                    raise FileNotFoundError("not found")
                import mimetypes as _mt
                ctype, _enc = _mt.guess_type(dp)
                with open(dp, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                if not q.get("view"):
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(os.path.basename(dp))}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(404, "not found")
            return
        # ---- extension routes (GET) ----
        if p.path in _EXT_GET:
            try:
                _EXT_GET[p.path](self, p.path, q)
            except Exception as _e:
                self._json({"ok": False, "error": str(_e)}, 500)
            return
        self.send_error(404)

    def do_POST(self):
        # route on the bare path so "?check=1" style query flags still match
        self._raw_path = self.path
        self._query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.path = urllib.parse.urlparse(self.path).path
        try:
            self._route_post()
        finally:
            self.path = self._raw_path

    def _route_post(self):
        if self.path == "/api/lock/verify":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            uid = str(body.get("id", "")).strip().lower()
            if uid and user_check(uid, body.get("password", "")):
                tok = secrets.token_hex(24)
                SESSIONS[tok] = {"user": uid, "exp": time.time() + SESSION_TTL}
                self._session_cookie(tok, SESSION_TTL)
            else:
                self._json({"ok": False, "error": "ভুল ID/পাসওয়ার্ড"}, 401)
            return
        if self.path == "/api/lock/register":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                actor = session_token(self.headers)
                uid = user_set(body.get("id", ""), body.get("password", ""), actor=actor)
                self._json({"ok": True, "id": uid})
            except Exception as e:
                code = 401 if str(e) == "locked" else 400
                self._json({"ok": False, "error": str(e)}, code)
            return
        if self.path == "/api/lock/passwd":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                actor = session_token(self.headers)
                if not actor:
                    self._json({"ok": False, "error": "locked"}, 401)
                    return
                user_set(actor, body.get("password", ""), actor=actor)
                try:
                    ck = self.headers.get("Cookie", "") or ""
                    m = re.search(r"atk_session=([0-9a-f]{48})", ck)
                    keep = m.group(1) if m else None
                    for t in [t for t in SESSIONS if t != keep]:
                        SESSIONS.pop(t, None)
                except Exception:
                    pass
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 400)
            return
        if self.path == "/api/lock/permanent":
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                if n > 0:
                    self.rfile.read(min(n, 65536))
                actor = session_token(self.headers)
                if not actor:
                    self._json({"ok": False, "error": "locked"}, 401)
                    return
                users = users_load()
                if actor not in users:
                    self._json({"ok": False, "error": "not found"}, 404)
                    return
                users[actor]["permanent"] = True
                users_save(users)
                self._json({"ok": True, "id": actor})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 400)
            return
        if self.path == "/api/lock/logout":
            try:
                ck = self.headers.get("Cookie", "") or ""
                m = re.search(r"atk_session=([0-9a-f]{48})", ck)
                if m:
                    SESSIONS.pop(m.group(1), None)
            except Exception:
                pass
            self._session_cookie("expired", 0)
            return
        if lock_on() and session_token(self.headers) is None:
            self._json({"ok": False, "error": "locked"}, 401)
            return
        if self.path == "/api/xl/save":
            from openpyxl import Workbook as _WB
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                raw = re.sub(r'[\\/:*?"<>|]', "_", str(body.get("file", "")).strip())
                if not raw.lower().endswith(".xlsx"):
                    raw += ".xlsx"
                if len(raw) < 6:
                    raise ValueError("invalid filename")
                sheets = body.get("sheets") or []
                if not sheets:
                    raise ValueError("empty workbook")
                dst = os.path.join(CUSTOM_DIR, os.path.basename(raw))
                bak = backup_file(dst) if os.path.isfile(dst) else None
                wbo = _WB()
                wbo.remove(wbo.active)
                used = set()
                for sh in sheets[:32]:
                    title = re.sub(r"[:\\/?*\[\]]", "_", str(sh.get("name", "Sheet"))[:31].strip()) or "Sheet"
                    base, k = title, 2
                    while title in used:
                        title = f"{base} {k}"
                        k += 1
                    used.add(title)
                    wso = wbo.create_sheet(title)
                    _merges = []
                    for _mg in (sh.get("merges") or [])[:200]:
                        try:
                            r1, c1, r2, c2 = [int(x) for x in _mg]
                            if 1 <= r1 <= r2 <= XL_MAX_ROWS and 1 <= c1 <= c2 <= XL_MAX_COLS and (r2 > r1 or c2 > c1):
                                _merges.append((r1, c1, r2, c2))
                        except Exception:
                            pass
                    _covered = set()
                    for (r1, c1, r2, c2) in _merges:
                        for _rr in range(r1, r2 + 1):
                            for _cc in range(c1, c2 + 1):
                                if (_rr, _cc) != (r1, c1):
                                    _covered.add((_rr, _cc))
                    for key, rawcell in (sh.get("cells") or {}).items():
                        try:
                            r, c = key.split(",")
                            r, c = int(r), int(c)
                        except (ValueError, AttributeError):
                            continue
                        if not (1 <= r <= XL_MAX_ROWS and 1 <= c <= XL_MAX_COLS):
                            continue
                        if (r, c) in _covered:
                            continue
                        try:
                            v, font, fill, align, bd, nf = xl_parse_cell(None, rawcell or {})
                            cell = wso.cell(r, c)
                            if isinstance(v, dict) and "__date__" in v:
                                try:
                                    from datetime import datetime as _dt
                                    v = _dt.fromisoformat(v["__date__"])
                                except Exception:
                                    v = str(v)
                            cell.value = v if v != "" else None
                            cell.font = font
                            cell.fill = fill
                            cell.alignment = align
                            cell.border = bd
                            if nf and nf != "General":
                                cell.number_format = nf
                        except Exception:
                            pass
                    for (r1, c1, r2, c2) in _merges:
                        try:
                            wso.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
                        except Exception:
                            pass
                wbo.save(dst)
                wbo.close()
                self._json({"ok": True, "file": os.path.basename(dst), "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/xl/delete":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                fname = os.path.basename(body.get("file", ""))
                path = os.path.join(CUSTOM_DIR, fname)
                if not (fname and os.path.isfile(path)):
                    raise FileNotFoundError("not found: " + fname)
                bak = backup_file(path)
                os.remove(path)
                self._json({"ok": True, "deleted": fname, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                m = re.search(r"boundary=(.+)", ctype)
                if not m:
                    raise ValueError("multipart expected")
                n = int(self.headers.get("Content-Length", 0))
                if n <= 0 or n > MAX_UPLOAD_BYTES + 1024:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 10MB)")
                raw = self.rfile.read(n)
                parts = parse_multipart(raw, m.group(1).strip().encode("ascii"))
                if "file" not in parts:
                    raise ValueError("কোনো ফাইল পাইনি")
                cli_name, data = parts["file"]
                safe = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(cli_name or "")).strip()
                if not safe.lower().endswith(".xlsx"):
                    raise ValueError("শুধু .xlsx Excel ফাইল আপলোড করুন")
                dst = os.path.join(INPUT_DIR, safe) if os.path.isdir(INPUT_DIR) else os.path.join(BASE, safe)
                cmp_target = dst if os.path.isfile(dst) else os.path.join(BASE, safe)
                existed = os.path.isfile(cmp_target)

                # --- safety gate: never silently drop hours/advance/gas ---
                # ?check=1  -> only report, do not write
                # ?force=1  -> user already saw the warning and confirmed
                qd = getattr(self, "_query", None) or {}
                dry = qd.get("check", ["0"])[0] == "1"
                force = qd.get("force", ["0"])[0] == "1"
                import tempfile as _tf
                tmp = os.path.join(_tf.gettempdir(), "_upcheck_%d.xlsx" % os.getpid())
                with open(tmp, "wb") as f:
                    f.write(data)
                rep = _upload_risk_report(tmp, cmp_target) if existed else {"safe": True, "lost": []}
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                if dry:
                    rep.update({"ok": True, "file": safe, "dry": True})
                    self._json(rep)
                    return
                if existed and not rep.get("safe") and not force:
                    rep.update({"ok": False, "blocked": True,
                                "error": "আপলোড করলে কিছু ডেটা হারিয়ে যাবে"})
                    self._json(rep, 409)
                    return

                bak = backup_file(dst) if os.path.isfile(dst) else (backup_file(cmp_target) if existed else None)
                with open(dst, "wb") as f:
                    f.write(data)
                # Keep BASE in sync too
                if os.path.isdir(INPUT_DIR):
                    try:
                        shutil.copy2(dst, os.path.join(BASE, safe))
                    except Exception:
                        pass
                try:
                    verify_written(dst)
                except Exception:
                    roll_back(dst, bak, existed)
                    raise
                repaired = _repair_site_rate_column(dst)
                grid = get_data_grid(dst)
                self._json({"ok": True, "file": safe, "backup": bak,
                            "workers": len(grid["rows"]), "risk": rep,
                            "repaired": repaired})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ocr-upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                m = re.search(r"boundary=(.+)", ctype)
                if not m:
                    raise ValueError("multipart expected")
                n = int(self.headers.get("Content-Length", 0))
                if n <= 0 or n > MAX_UPLOAD_BYTES + 1024:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 10MB)")
                raw = self.rfile.read(n)
                parts = parse_multipart(raw, m.group(1).strip().encode("ascii"))
                if "file" not in parts:
                    raise ValueError("কোনো ফাইল পাইনি")
                cli_name, data = parts["file"]
                safe = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(cli_name or "")).strip()
                if not re.search(r"\.(jpe?g|png|pdf)$", safe, re.I):
                    raise ValueError("শুধু JPG/PNG/PDF দিন")
                dst = os.path.join(OCR_DIR, safe)
                with open(dst, "wb") as f:
                    f.write(data)
                missing = []
                import importlib
                _Img = None
                try:
                    _pil_image = importlib.import_module("PIL.Image")
                    _Img = _pil_image
                except Exception:
                    missing.append("pillow")

                _pt = None
                try:
                    _pt = importlib.import_module("pytesseract")
                except Exception:
                    missing.append("pytesseract")

                if shutil.which("tesseract") is None:
                    missing.append("Tesseract-OCR (Windows installer)")

                _fz = None
                if safe.lower().endswith(".pdf"):
                    try:
                        _fz = importlib.import_module("fitz")
                    except Exception:
                        missing.append("pymupdf (PDF পড়তে)")

                if missing or _Img is None or _pt is None:
                    self._json({"ok": False, "error": "OCR সেটআপ বাকি (" + ", ".join(missing) + ") — ফাইল ocr_uploads-এ জমা আছে"})
                    return

                # Best-effort text preview (grid mapping = next step)
                if safe.lower().endswith(".pdf") and _fz is not None:
                    doc = _fz.open(dst)
                    page = doc[0]
                    pix = page.get_pixmap(dpi=150)
                    import io as _io
                    img = _Img.open(_io.BytesIO(pix.tobytes("png")))
                else:
                    img = _Img.open(dst)
                text = _pt.image_to_string(img, lang="eng")[:2000]
                self._json({"ok": True, "file": safe, "text": text,
                            "note": "টেক্সট প্রিভিউ — গ্রিড ম্যাপিং পরের ধাপ"})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/file-remove":
            # Data লিস্ট থেকে পুরনো ফাইল সরান — ফাইল মুছে যায় না, ব্যাকআপে যায় (Backup ট্যাব থেকে ফেরত আনা যায়)
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                fname = os.path.basename(body.get("file", ""))
                if not fname.lower().endswith(".xlsx"):
                    raise ValueError("শুধু .xlsx ফাইল লিস্ট থেকে সরানো যায়")
                src = os.path.join(INPUT_DIR, fname) if os.path.isdir(INPUT_DIR) and os.path.isfile(os.path.join(INPUT_DIR, fname)) else os.path.join(BASE, fname)
                if not os.path.isfile(src):
                    raise FileNotFoundError(fname)
                bak = backup_file(src)  # আগে ব্যাকআপ, তারপরই লিস্ট থেকে সরান
                os.remove(src)
                if os.path.isdir(INPUT_DIR) and os.path.isfile(os.path.join(BASE, fname)):
                    try:
                        os.remove(os.path.join(BASE, fname))
                    except Exception:
                        pass
                _src = INPUT_DIR if os.path.isdir(INPUT_DIR) else BASE
                xlsx = [f for f in os.listdir(_src) if f.lower().endswith(".xlsx")]
                self._json({"ok": True, "file": fname, "backup": bak,
                            "data": [f for f in xlsx if "total" not in f.lower()],
                            "all": xlsx})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/cycle-toggle":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                import cycle as _cy
                ym = str(body.get("month") or "")
                if not re.match(r"^\d{4}-\d{2}$", ym):
                    raise ValueError("invalid month")
                key = str(body.get("key") or "")
                if key not in ("siteFile", "checked", "cleared", "inv"):
                    raise ValueError("invalid step")
                s2 = _cy.toggle(ym, key, provider=body.get("provider"),
                                value=body.get("value"),
                                no=body.get("no"), amount=body.get("amount"))
                self._json({"ok": True, "month": ym, "state": s2})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path in ("/api/reimport-preview", "/api/reimport"):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                import reimport as _ri
                total = body.get("total") or ""
                data = body.get("data") or ""
                # accept the bot's own output file, or a copy saved elsewhere
                tp = os.path.join(OUT_DIR, os.path.basename(total))
                if not os.path.isfile(tp):
                    cand = body.get("totalPath") or ""
                    if cand and os.path.isfile(cand):
                        tp = cand
                    else:
                        raise FileNotFoundError(
                            "\u0981\u09aa\u09be\u0995\u09be\u09b0 Total T \u09ab\u09be\u0987\u09b2 \u09aa\u09be\u0981\u09a4\u09be \u09b0\u09be\u0996\u09c1\u09a8 \u09af\u09be\u09af\u09bc \u0985\u09b5\u09cd\u09af\u09b0 \u0995\u09cb\u09a1\u09be")
                dp = resolve_file(data) if data else resolve_file(
                    (body.get("dataFile") or ""))
                dry = self.path.endswith("-preview")
                if dry:
                    self._json({"ok": True, "preview": True,
                                "source": os.path.basename(tp),
                                "changes": _ri.reimport(tp, dp, dry_run=True)})
                    return
                bak = backup_file(dp)              # always backup first
                ch = _ri.reimport(tp, dp,
                                  apply_days=bool(body.get("days", True)),
                                  apply_grand=bool(body.get("grand", True)))
                try:
                    verify_written(dp)
                except Exception as ve:
                    roll_back(dp, bak, True)
                    raise ValueError("\u09ab\u09be\u0987\u09b2\u0947 \u09b0\u09be\u0996\u09c1\u09a8 \u09af\u09be\u09af\u09bc\u09c7\u0996\u09c1\u09a8 \u0986\u09b0\u09c7\u09b0 \u09aa\u09b0\u09bf\u09b8\u09cd\u09a5\u09be\u09af\u09bc\u09c7\u0996\u09c7\u09b0\u0993 \u09ab\u09c7\u09b0\u09be\u09a8\u09cb \u09b9\u09af\u09bc\u09c7\u099b\u09c7 (%s)" % ve)
                self._json({"ok": True, "source": os.path.basename(tp),
                            "backup": bak, "changes": ch})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/month-clear":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                import months as _months
                import botmem
                data = resolve_file(body.get("file") or "")
                tmpl = resolve_file(body.get("tmpl") or "")
                month = int(body.get("month") or 9)
                year = int(body.get("year") or 2026)
                do_gen = body.get("doGenerate", True)
                try:
                    from generator import analyze_data_sheet
                    if not (analyze_data_sheet(data).get("workers") or []):
                        raise ValueError(
                            "ডেটা শিটে কোনো লোক নেই — মাস ক্লিয়ার বাতিল। "
                            "সঠিক ডেটা ফাইলটি বেছে নিন")
                except ImportError:
                    pass
                res = _months.month_clear(data, tmpl, month, year,
                                          do_generate=do_gen,
                                          backup_fn=lambda p: backup_file(p))
                mem = botmem.mem_save({
                    "defMonth": res["newMonthNum"], "defYear": res["newYear"],
                    "profitMonth": "%04d-%02d" % (res["newYear"], res["newMonthNum"]),
                    "dataFile": res["newFile"],
                    "lastMonthRollover": botmem.stamp()})
                try:
                    self._json({"ok": True, "memory": mem, **res})
                except Exception:
                    self._json({"ok": False,
                                "error": "মাস ক্লিয়ার হয়েছে, কিন্তু নতুন মাসের নাম "
                                         "সেভ হয়নি: %s\n\n%s" % (res["newName"],
                                                               res["newFile"])})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path in ("/api/memory", "/api/memory-reset", "/api/month-roll"):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                import botmem
                if self.path == "/api/memory-reset":
                    self._json({"ok": True, "memory": botmem.mem_reset()})
                    return
                if self.path == "/api/memory":
                    self._json({"ok": True, "memory": botmem.mem_save(body)})
                    return
                # ---- month roll: new month on the same data sheet ----
                path = resolve_file(body.get("file", ""))
                month = int(body.get("month", 9))
                year = int(body.get("year", 2026))
                # doArchive=False -> copy nothing; True/absent -> archive the
                # month we are LEAVING (defaults to the month before `month`)
                do_arch = body.get("doArchive", True)
                arch = []
                if do_arch:
                    arch = body.get("archive") or []
                    if not arch:
                        pm = month - 1 or 12
                        py = year if month > 1 else year - 1
                        arch = ["%02d-%d" % (pm, py)]
                bak = backup_file(path)          # always backup before work
                res = botmem.month_roll(path, month, year, arch)
                try:
                    verify_written(path)
                except Exception as ve:
                    roll_back(path, bak, True)
                    raise ValueError("\u09b8\u09c7\u09ad \u0995\u09b0\u09be \u09af\u09be\u09af\u09bc\u09c7, \u09ab\u09be\u0987\u09b2\u09c7 \u0986\u0997\u09c7\u09b0 \u0985\u09ac\u09b8\u09cd\u09a5\u09be\u09b0 \u09ab\u09c7\u09b0\u09be\u09a8\u09cb \u09b9\u09af\u09bc\u09c7\u099b\u09c7 (%s)" % ve)
                mem = botmem.mem_save({
                    "defMonth": month, "defYear": year,
                    "profitMonth": "%04d-%02d" % (year, month),
                    "lastMonthRollover": botmem.stamp()})
                self._json({"ok": True, "backup": bak, "memory": mem, **res})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/data-save":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                path = resolve_file(body.get("file", ""))
                rows = body.get("rows", [])
                # Excel ফাইলটা খোলা থাকলে সেভ চুপচাপ হারিয়ে যায়
                lock = os.path.join(os.path.dirname(path), "~$" + os.path.basename(path))
                locked = os.path.isfile(lock)
                # গুরুত্বপূর্ণ ফাইলে ব্যাকআপ সবসময় — টগল বন্ধ করা হয়েছে
                bak = backup_file(path)  # backup BEFORE work, always
                res = save_data_sheet(path, path, rows)
                try:
                    verify_written(path)
                except Exception as e:
                    roll_back(path, bak, True)
                    raise ValueError("সেভ করা যায়নি, ফাইল আগের অবস্থায় ফেরানো হয়েছে (%s)" % e)
                # ---- ভেরিফিকেশন: ডিস্ক থেকে আবার পড়ে দেখি আসলেই লেখা হয়েছে কিনা ----
                mismatch = []
                try:
                    after = get_data_grid(path)
                    disk = {str(w.get("name") or "").strip().upper(): w
                            for w in after.get("rows", [])}
                    for w in rows:
                        nm = str(w.get("name") or "").strip().upper()
                        if not nm:
                            continue
                        d = disk.get(nm)
                        if d is None:
                            mismatch.append({"name": w.get("name"), "field": "row",
                                             "sent": "present", "disk": "MISSING"})
                            continue
                        for fld in ("rate", "advance", "gas"):
                            sv, dv = w.get(fld), d.get(fld)
                            sn_ = "" if sv in (None, "") else str(sv).strip()
                            dn_ = "" if dv in (None, "") else str(dv).strip()
                            try:
                                same = abs(float(sn_) - float(dn_)) < 1e-6
                            except ValueError:
                                same = sn_ == dn_
                            if not same:
                                mismatch.append({"name": w.get("name"), "field": fld,
                                                 "sent": sv, "disk": dv})
                except Exception as ve:
                    mismatch.append({"name": "-", "field": "verify",
                                     "sent": "-", "disk": str(ve)})
                self._json({"ok": True, "backup": bak, "locked": locked,
                            "verified": not mismatch, "mismatch": mismatch, **res})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/restore":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                bak = os.path.basename(body.get("backup", ""))
                dest = os.path.basename(body.get("dest", ""))
                src = os.path.join(BACKUP_DIR, bak)
                if not (bak and os.path.isfile(src)):
                    raise FileNotFoundError("backup not found: " + bak)
                if not (dest and dest.lower().endswith(".xlsx")):
                    raise ValueError("invalid destination")
                dst = os.path.join(BASE, dest)
                pre = backup_file(dst) if os.path.isfile(dst) else None  # backup before restore too
                shutil.copy2(src, dst)
                self._json({"ok": True, "restored": dest, "pre_restore_backup": pre})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/save-as":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                src_dir = CUSTOM_DIR if body.get("src") == "custom" else OUT_DIR
                fname = os.path.basename(body.get("file", ""))
                src = os.path.join(src_dir, fname)
                if not (fname and os.path.isfile(src)):
                    raise FileNotFoundError("output not found: " + fname)
                name = re.sub(r'[\\/:*?"<>|]', "_", str(body.get("name", "")).strip())
                if not name.lower().endswith(".xlsx"):
                    name += ".xlsx"
                if len(name) < 6:
                    raise ValueError("invalid filename")
                folder = str(body.get("folder", "")).strip().strip('"')
                if not os.path.isabs(folder):
                    raise ValueError("লোকেশন পুরো পাথ হতে হবে, যেমন D:\\Reports")
                dst, bak, tagged = safe_copy_out(src, os.path.join(folder, name))
                self._json({"ok": True, "saved": dst, "backup": bak,
                            "bot_copy_renamed": tagged})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/od/mkdir":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                rp = rc_path(body.get("path", ""))
                name = re.sub(r'[\\/:*?"<>|]', "_", str(body.get("name", "")).strip()).strip(" .")
                if not name:
                    raise ValueError("invalid folder name")
                dest = (rp + "/" + name) if rp else name
                rc_run("mkdir", RC_REMOTE + dest, timeout=120)
                self._json({"ok": True, "name": name})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:200]}, 500)
            return
        if self.path == "/api/od/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                m = re.search(r"boundary=(.+)", ctype)
                if not m:
                    raise ValueError("multipart expected")
                n = int(self.headers.get("Content-Length", 0))
                if n <= 0 or n > DRIVE_MAX_BYTES + 65536:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 100MB)")
                raw = self.rfile.read(n)
                parts = parse_multipart(raw, m.group(1).strip().encode("ascii"))
                if "file" not in parts:
                    raise ValueError("কোনো ফাইল পাইনি")
                cli_name, data = parts["file"]
                safe = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(cli_name or "")).strip().strip(" .")
                if not safe or len(data) == 0:
                    raise ValueError("invalid file")
                if len(data) > DRIVE_MAX_BYTES:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 100MB)")
                if os.path.splitext(safe)[1].lower() in BLOCKED_EXT:
                    raise ValueError("এই ধরনের ফাইল (.exe/.bat) রাখা যাবে না")
                _pp = parts.get("path")
                rp = rc_path(_pp[1].decode("utf-8", "replace") if _pp else "")
                import tempfile as _tf
                with _tf.NamedTemporaryFile(delete=False, suffix="_" + safe) as tf:
                    tf.write(data)
                    tmp = tf.name
                try:
                    # ক্লাউডে আগের ফাইলটা যেন চুপচাপ না হারায়: নাম থাকলে
                    # নতুন নাম বানাই, পুরনো ফাইল অক্ষত থাকে
                    dest = (rp + "/" + safe) if rp else safe
                    if rc_exists(RC_REMOTE + dest):
                        base, ext = os.path.splitext(safe)
                        k = 2
                        prefix = (rp + "/") if rp else ""
                        while rc_exists(RC_REMOTE + prefix + "{0} ({1}){2}".format(base, k, ext)):
                            k += 1
                        safe = "{0} ({1}){2}".format(base, k, ext)
                        dest = prefix + safe
                    rc_run("copyto", tmp, RC_REMOTE + dest, timeout=300)
                finally:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                self._json({"ok": True, "file": safe, "size": len(data)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:200]}, 500)
            return
        if self.path == "/api/od/delete":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                rp = rc_path(body.get("path", ""))
                if not rp:
                    raise ValueError("root মুছতে পারবেন না")
                if body.get("kind") == "folder":
                    rc_run("purge", RC_REMOTE + rp, timeout=300)
                else:
                    rc_run("delete", RC_REMOTE + rp, timeout=300)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)[:200]}, 500)
            return
        if self.path == "/api/drive/mkdir":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                name = re.sub(r'[\\/:*?"<>|]', "_", str(body.get("name", "")).strip()).strip(" .")
                if not name:
                    raise ValueError("invalid folder name")
                dp = drive_path(body.get("path", ""))
                if not os.path.isdir(dp):
                    raise FileNotFoundError("folder not found")
                os.makedirs(os.path.join(dp, name), exist_ok=True)
                self._json({"ok": True, "name": name})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/upload":
            try:
                ctype = self.headers.get("Content-Type", "")
                m = re.search(r"boundary=(.+)", ctype)
                if not m:
                    raise ValueError("multipart expected")
                n = int(self.headers.get("Content-Length", 0))
                if n <= 0 or n > DRIVE_MAX_BYTES + 65536:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 100MB)")
                raw = self.rfile.read(n)
                parts = parse_multipart(raw, m.group(1).strip().encode("ascii"))
                if "file" not in parts:
                    raise ValueError("কোনো ফাইল পাইনি")
                cli_name, data = parts["file"]
                safe = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(cli_name or "")).strip().strip(" .")
                if not safe or len(data) == 0:
                    raise ValueError("invalid file")
                if len(data) > DRIVE_MAX_BYTES:
                    raise ValueError("ফাইল বড় (সর্বোচ্চ 100MB)")
                if os.path.splitext(safe)[1].lower() in BLOCKED_EXT:
                    raise ValueError("এই ধরনের ফাইল (.exe/.bat) রাখা যাবে না")
                _pp = parts.get("path")
                dp = drive_path(_pp[1].decode("utf-8", "replace") if _pp else "")
                if not os.path.isdir(dp):
                    raise FileNotFoundError("folder not found")
                dst = os.path.join(dp, safe)
                if os.path.exists(dst):
                    base, ext = os.path.splitext(safe)
                    k = 2
                    while os.path.exists(dst):
                        dst = os.path.join(dp, f"{base} ({k}){ext}")
                        k += 1
                with open(dst, "wb") as f:
                    f.write(data)
                self._json({"ok": True, "file": os.path.basename(dst), "size": len(data)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/delete":
            # Safe delete: move to Trash, never permanent from here
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                dp = drive_path(body.get("path", ""))
                base = os.path.normpath(DRIVE_DIR)
                if os.path.normpath(dp) == base:
                    raise ValueError("root মুছতে পারবেন না")
                if not os.path.exists(dp):
                    raise FileNotFoundError("not found")
                from datetime import datetime as _dt
                ts = _dt.now().strftime("%Y%m%d_%H%M%S")
                tname = ts + "__" + os.path.basename(dp)
                tdst = os.path.join(TRASH_DIR, tname)
                k = 2
                while os.path.exists(tdst):
                    tdst = os.path.join(TRASH_DIR, ts + "_" + str(k) + "__" + os.path.basename(dp))
                    k += 1
                shutil.move(dp, tdst)
                m = trash_load()
                m[os.path.basename(tdst)] = {"orig": body.get("path", ""),
                                             "isdir": os.path.isdir(tdst),
                                             "time": ts}
                trash_save(m)
                self._json({"ok": True, "trash": os.path.basename(tdst)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/trash":
            try:
                m = trash_load()
                items = []
                for tn, info in m.items():
                    p = os.path.join(TRASH_DIR, tn)
                    if not os.path.exists(p):
                        continue
                    try:
                        sz = 0
                        if os.path.isfile(p):
                            sz = os.path.getsize(p)
                        else:
                            for _r, _ds, _fs in os.walk(p):
                                for _f in _fs:
                                    try:
                                        sz += os.path.getsize(os.path.join(_r, _f))
                                    except OSError:
                                        pass
                        items.append({"name": tn, "orig": info.get("orig", ""),
                                      "isdir": info.get("isdir", False),
                                      "time": info.get("time", ""), "size": sz})
                    except OSError:
                        pass
                items.sort(key=lambda x: x["time"], reverse=True)
                self._json({"ok": True, "items": items})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/restore-trash":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                tn = os.path.basename(body.get("name", ""))
                m = trash_load()
                if tn not in m:
                    raise FileNotFoundError("trash-এ নেই")
                src = os.path.join(TRASH_DIR, tn)
                if not os.path.exists(src):
                    del m[tn]
                    trash_save(m)
                    raise FileNotFoundError("trash-এ নেই")
                try:
                    dp = drive_path(m[tn].get("orig", ""))
                except ValueError:
                    dp = os.path.join(os.path.normpath(DRIVE_DIR),
                                      os.path.basename(src).split("__", 1)[-1])
                if os.path.exists(dp):
                    base, ext = os.path.splitext(dp)
                    k = 2
                    while os.path.exists(dp):
                        dp = f"{base} ({k}){ext}"
                        k += 1
                os.makedirs(os.path.dirname(dp), exist_ok=True)
                shutil.move(src, dp)
                del m[tn]
                trash_save(m)
                self._json({"ok": True, "restored": dp})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/empty-trash":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                if not body.get("confirm"):
                    raise ValueError("confirm দরকার")
                n_rm, freed = 0, 0
                for fn in os.listdir(TRASH_DIR):
                    if fn == "trash.json":
                        continue
                    p = os.path.join(TRASH_DIR, fn)
                    try:
                        if os.path.isfile(p):
                            freed += os.path.getsize(p)
                            os.remove(p)
                        elif os.path.isdir(p):
                            for _r, _ds, _fs in os.walk(p):
                                for _f in _fs:
                                    try:
                                        freed += os.path.getsize(os.path.join(_r, _f))
                                    except OSError:
                                        pass
                            shutil.rmtree(p)
                        n_rm += 1
                    except OSError:
                        pass
                trash_save({})
                self._json({"ok": True, "removed": n_rm, "freed_bytes": freed})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/drive/rename":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                dp = drive_path(body.get("path", ""))
                base = os.path.normpath(DRIVE_DIR)
                if os.path.normpath(dp) == base:
                    raise ValueError("root-এর নাম বদলানো যাবে না")
                if not os.path.exists(dp):
                    raise FileNotFoundError("not found")
                name = re.sub(r'[\\/:*?"<>|]', "_", str(body.get("name", "")).strip()).strip(" .")
                if not name:
                    raise ValueError("invalid name")
                if os.path.isfile(dp) and os.path.splitext(name)[1].lower() in BLOCKED_EXT:
                    raise ValueError("এই ধরনের নাম রাখা যাবে না")
                dst = os.path.join(os.path.dirname(dp), name)
                if os.path.exists(dst):
                    raise ValueError("এই নামে already আছে")
                bak = backup_file(dp) if os.path.isfile(dp) else None
                os.rename(dp, dst)
                self._json({"ok": True, "name": name, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/phones":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                d = phones_load()
                if body.get("set") is not None:
                    person = " ".join(str(body.get("person", "")).split())
                    if not person:
                        raise ValueError("নাম দিন")
                    num = wa_number(body.get("set"))
                    if num:
                        d[person] = num
                    else:
                        d.pop(person, None)
                    bak = phones_save(d)
                    self._json({"ok": True, "person": person,
                                "phone": d.get(person, ""), "backup": bak,
                                "total": len(d)})
                else:
                    self._json({"ok": True, "phones": phones_load()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/profit-rates":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                d = rates_load()
                site = " ".join(str(body.get("site", "")).split())
                if not site:
                    raise ValueError("সাইটের নাম দিন")
                if body.get("del"):
                    d.pop(site, None)
                else:
                    try:
                        rate = float(str(body.get("rate", "")).replace(",", "").strip())
                    except (TypeError, ValueError):
                        raise ValueError("সঠিক রেট লিখুন")
                    if rate < 0:
                        raise ValueError("সঠিক রেট লিখুন")
                    d[site] = rate
                bak = rates_save(d)
                self._json({"ok": True, "rates": d, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/profit-srates":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                d = srates_load()
                person = " ".join(str(body.get("person", "")).split())
                if not person:
                    raise ValueError("লোকের নাম দিন")
                key = norm_person(person)
                if not key:
                    raise ValueError("লোকের নাম দিন")
                if body.get("del"):
                    d.pop(key, None)
                else:
                    try:
                        rate = float(str(body.get("rate", "")).replace(",", "").strip())
                    except (TypeError, ValueError):
                        raise ValueError("সঠিক রেট লিখুন")
                    if rate <= 0:
                        raise ValueError("সঠিক রেট লিখুন")
                    d[key] = {"name": person, "rate": rate}
                bak = srates_save(d)
                self._json({"ok": True, "srates": d, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/profit-duty":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                d = duty_load()
                month = " ".join(str(body.get("month", "")).split())[:7]
                person = " ".join(str(body.get("person", "")).split())
                if not month or not person:
                    raise ValueError("মাস ও নাম দিন")
                key = norm_person(person)
                if not key:
                    raise ValueError("লোকের নাম দিন")
                m = d.get(month) or {}
                if body.get("del"):
                    m.pop(key, None)
                    if m:
                        d[month] = m
                    else:
                        d.pop(month, None)
                else:
                    raw = body.get("splits") or []
                    if not isinstance(raw, list) or not raw:
                        raise ValueError("সাইট ভাগ দিন")
                    splits = []
                    for sp in raw:
                        site = " ".join(str((sp or {}).get("site", "")).split())[:60]
                        try:
                            days = float(str((sp or {}).get("days", "")))
                        except (TypeError, ValueError):
                            days = 0
                        try:
                            hours = float(str((sp or {}).get("hours", "")))
                        except (TypeError, ValueError):
                            hours = 0
                        if not site:
                            raise ValueError("সাইটের নাম দিন")
                        if days < 0 or hours < 0:
                            raise ValueError("সঠিক সংখ্যা লিখুন")
                        splits.append({"site": site, "days": days, "hours": hours})
                    m[key] = {"name": person, "splits": splits}
                    d[month] = m
                bak = duty_save(d)
                self._json({"ok": True, "duty": d, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/profit-exp":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                lst = exp_load()
                if body.get("del") is not None:
                    idx = int(body.get("del"))
                    if not (0 <= idx < len(lst)):
                        raise ValueError("এন্ট্রি পাইনি")
                    lst.pop(idx)
                else:
                    month = " ".join(str(body.get("month", "")).split())[:7]
                    label = " ".join(str(body.get("label", "")).split())[:60]
                    try:
                        amt = float(str(body.get("amount", "")).replace(",", "").strip())
                    except (TypeError, ValueError):
                        raise ValueError("সঠিক টাকা লিখুন")
                    if not label:
                        raise ValueError("খরচের নাম দিন")
                    if amt <= 0:
                        raise ValueError("সঠিক টাকা লিখুন")
                    lst.append({"month": month, "label": label, "amount": amt})
                bak = exp_save(lst)
                self._json({"ok": True, "expenses": lst, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/profit-pay":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                d = pay_load()
                month = " ".join(str(body.get("month", "")).split())[:7]
                if not month:
                    raise ValueError("মাস দিন")
                kind = str(body.get("kind", ""))
                paid = bool(body.get("paid"))
                m = d.get(month) or {"income": False, "clear": {}, "prov": {}}
                day = " ".join(str(body.get("date", "")).split())[:10]
                if paid and not day:
                    import datetime as _dt
                    day = _dt.date.today().isoformat()
                if kind == "income":
                    m["income"] = {"paid": True, "date": day} if paid else False
                elif kind == "clear":
                    prov = " ".join(str(body.get("provider", "")).split())
                    if not prov:
                        raise ValueError("প্রোভাইডার দিন")
                    if not isinstance(m.get("clear"), dict):
                        m["clear"] = {}
                    if paid:
                        m["clear"][prov] = {"paid": True, "date": day}
                    else:
                        m["clear"].pop(prov, None)
                elif kind == "prov":
                    prov = " ".join(str(body.get("provider", "")).split())
                    if not prov:
                        raise ValueError("প্রোভাইডার দিন")
                    if not isinstance(m.get("prov"), dict):
                        m["prov"] = {}
                    if paid:
                        m["prov"][prov] = {"paid": True, "date": day}
                    else:
                        m["prov"].pop(prov, None)
                else:
                    raise ValueError("ধরন ঠিক নেই")
                d[month] = m
                if not m.get("income") and not m.get("clear") and not m.get("prov"):
                    d.pop(month, None)
                bak = pay_save(d)
                self._json({"ok": True, "pay": d, "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/labor-save":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                from openpyxl.comments import Comment as _Cmt
                from openpyxl.styles import Alignment as _Al
                fp = labor_ensure()
                bak = backup_file(fp)
                before = cellsnap(fp)
                cbefore = commentsnap(fp)
                from openpyxl import load_workbook as _LW
                wb = _LW(fp)
                ws = wb["Sheet1"]
                blocks = labor_blocks(ws)
                act = str(body.get("act", ""))
                touched = set()
                info = {}

                def _free_row(nc):
                    mr = ws.merged_cells.ranges
                    for r in range(5, (ws.max_row or 0) + 30):
                        if all(ws.cell(r, c).value in (None, "")
                               for c in range(nc, nc + LABOR_W)):
                            bad = False
                            for m in mr:
                                if m.min_row <= r <= m.max_row and not (
                                        m.max_col < nc or m.min_col > nc + LABOR_W - 1):
                                    bad = True
                                    break
                            if not bad:
                                return r
                    return None

                if act == "add":
                    prov = _nmv(body.get("provider"))
                    name = _nmv(body.get("name"))
                    if not name:
                        raise ValueError("লোকের নাম লিখুন")
                    nc = None
                    for c in blocks:
                        if _nmv(ws.cell(2, c).value) == prov:
                            nc = c
                            break
                    if nc is None:
                        if not prov:
                            raise ValueError("প্রোভাইডারের নাম লিখুন")
                        # নতুন প্রোভাইডার: ফাইলের নিজস্ব ফরম্যাট অনুসরণ করে ব্লক বানাই
                        nc = labor_free_block_col(ws, blocks)
                        if nc is None:
                            raise ValueError("ফাইলে আর জায়গা নেই — এক্সেলে একটা "
                                             "ফাঁকা হলুদ ব্লক বানিয়ে দিন")
                        labor_make_block(ws, nc, prov)
                        touched |= {(2, c) for c in range(nc, nc + LABOR_W)}
                        touched |= {(4, c) for c in range(nc, nc + LABOR_W)}
                        blocks = labor_blocks(ws)
                    tr = _free_row(nc)
                    if tr is None:
                        raise ValueError("এই প্রোভাইডারের জন্য খালি সারি নেই")
                    vals = [name, _as_date(body.get("start", "")),
                            _as_num(body.get("rate", "")), body.get("site", "")]
                    for i, v in enumerate(vals):
                        if v not in (None, ""):
                            ws.cell(tr, nc + i).value = v
                            touched.add((tr, nc + i))
                    # তারিখ ঘরে আপনার ফরম্যাট: 16-Oct-26
                    if vals[1] not in (None, ""):
                        ws.cell(tr, nc + 1).number_format = "d-mmm-yy"
                    info = {"row": tr, "col": nc}

                elif act in ("edit", "comment"):
                    nc = int(body.get("col", 0))
                    r = int(body.get("row", 0))
                    if nc not in blocks or not (5 <= r <= (ws.max_row or 0) + 5):
                        raise ValueError("সারি/কলাম ঠিক নেই")
                    if act == "edit":
                        vals = body.get("values") or {}
                        fields = {"name": 0, "start": 1, "rate": 2, "site": 3}
                        for fld in ("name", "start", "rate", "site"):
                            if fld not in vals:
                                continue
                            off = fields[fld]
                            v = vals[fld]
                            if fld == "start":
                                v = _as_date(v)
                                if v == "":
                                    v = None
                            elif fld == "rate":
                                v = _as_num(v)
                                if v == "":
                                    v = None
                            cell = ws.cell(r, nc + off)
                            if type(cell).__name__ == "MergedCell":
                                raise ValueError("এই ঘরটা মার্জড, এখানে লেখা যাবে না")
                            cell.value = v if v not in ("", None) else None
                            if fld == "start" and v is not None:
                                cell.number_format = "d-mmm-yy"
                            touched.add((r, nc + off))
                    # ডিউটির ইতিহাস: তারিখের ঘরে (আর সাইটের ঘরে আলাদা)
                    # — যেকোনো একটা act ('edit' বা 'comment') এটা করতে পারে
                    for key, off in (("comment", 1), ("siteComment", 3)):
                        if body.get(key) is None:
                            continue
                        ccell = ws.cell(r, nc + off)
                        if type(ccell).__name__ == "MergedCell":
                            raise ValueError("এই ঘরটা মার্জড")
                        ccell.comment = None
                        ct = str(body.get(key) or "").strip()
                        if ct:
                            ccell.comment = _Cmt(ct, "Bot")
                        touched.add((r, nc + off))
                    if body.get("text") is not None:
                        dcell = ws.cell(r, nc + 1)
                        if type(dcell).__name__ == "MergedCell":
                            raise ValueError("তারিখের ঘরটা মার্জড")
                        dcell.comment = None
                        tx = str(body.get("text") or "").strip()
                        if tx:
                            dcell.comment = _Cmt(tx, "Bot")
                        touched.add((r, nc + 1))
                    if act == "edit":
                        touched.add((r, nc))

                elif act == "del":
                    nc = int(body.get("col", 0))
                    r = int(body.get("row", 0))
                    if nc not in blocks or not (5 <= r <= (ws.max_row or 0) + 5):
                        raise ValueError("সারি/কলাম ঠিক নেই")
                    nm = _nmv(ws.cell(r, nc).value)
                    if not nm:
                        raise ValueError("এখানে কোনো লোক নেই")
                    for c in range(nc, nc + LABOR_W):
                        try:
                            cl = ws.cell(r, c)
                            if type(cl).__name__ == "MergedCell":
                                continue
                            cl.comment = None
                            cl.value = None
                            touched.add((r, c))
                        except Exception:
                            pass
                    info = {"removed": nm}

                else:
                    raise ValueError("কাজটা বোঝা গেল না")

                wb.save(fp)
                wb.close()
                # যাচাই না হওয়া পর্যন্ত কোনো লেখা ধরে রাখা হবে না
                try:
                    if not restore_parts(fp):
                        raise ValueError("parts")
                    verify_written(fp)
                    comment_guard(fp, bak, cbefore, touched)
                    write_guard(fp, bak, before, touched)
                except Exception:
                    shutil.copy2(bak, fp)
                    restore_parts(fp)
                    raise
                self._json({"ok": True, "backup": bak, **info})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/labor-refresh":
            try:
                import shutil as _sh
                master = os.path.join(LABOR_DIR, LABOR_MASTER)
                _sh.copy2(master, LABOR_FILE)
                preserve_snapshot(LABOR_FILE)
                self._json({"ok": True, "file": os.path.basename(LABOR_FILE)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/labor-assign":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                person = " ".join(str(body.get("person", "")).split())
                provider = " ".join(str(body.get("provider", "")).split())
                if not person:
                    raise ValueError("নাম দিন")
                d = assign_load()
                if provider:
                    d[person] = provider
                else:
                    d.pop(person, None)
                bak = assign_save(d)
                self._json({"ok": True, "person": person,
                            "provider": d.get(person, ""), "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/provider-save":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                provider = " ".join(str(body.get("provider", "")).split())
                sheet_name = str(body.get("sheet_name", "")).strip() or None
                header_text = str(body.get("header_text", "")).strip() or None
                if not provider:
                    raise ValueError("প্রোভাইডার দিন")
                d = provider_config_load()
                if header_text is None:
                    header_text = "Refarenc of ( {0} )".format(provider)
                d[provider] = {"sheet": sheet_name, "header": header_text}
                bak = provider_config_save(d)
                self._json({"ok": True, "provider": provider,
                            "sheet": sheet_name, "header": header_text,
                            "backup": bak})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/ws/advance-add":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                from openpyxl import load_workbook as _lw3
                fp = advance_ensure()
                if not os.path.isfile(fp):
                    raise FileNotFoundError(ADV_BOT + " নেই")
                person = " ".join(str(body.get("person", "")).split())
                if not person:
                    raise ValueError("নাম দিন")
                try:
                    amt = float(str(body.get("amount", "")).replace(",", "").strip())
                except Exception:
                    raise ValueError("সঠিক টাকা লিখুন")
                if amt <= 0:
                    raise ValueError("সঠিক টাকা লিখুন")
                date = str(body.get("date", "")).strip()[:20]
                paid = bool(body.get("paid"))
                reason = " ".join(str(body.get("reason", "")).split())[:500]
                bak = backup_file(fp)
                before = cellsnap(fp)
                wb = _lw3(fp)
                ws = wb["Sheet1"]
                blocks = []
                for c in range(1, (ws.max_column or 0) + 1):
                    if " ".join(str(ws.cell(4, c).value or "").split()).lower() == "name":
                        blocks.append((c, c + 1, c + 2, c + 3, c + 4))
                if not blocks:
                    raise ValueError("হেডার পাইনি")

                def _k(s):
                    return re.sub(r"\s*\(.*", "", " ".join(str(s or "").split())).strip().lower()

                def _nm(v):
                    return " ".join(str(v or "").split())

                want = _k(person)
                found = None
                for b in blocks:
                    nc = b[0]
                    last = None
                    for r in range(5, (ws.max_row or 0) + 1):
                        nm = " ".join(str(ws.cell(r, nc).value or "").split())
                        if not nm:
                            continue
                        s = nm.lower()
                        if s.startswith("total") or s.startswith("grand balance"):
                            continue
                        if _k(nm) == want:
                            last = r
                    if last:
                        found = (b, last)
                        break
                is_new_person = False
                if not found:
                    # নতুন লোক: খালি ব্লকে একটি ফাঁকা সারিতে নাম বসিয়ে দিই।
                    # পার্সার নাম দিলে তার ব্লকে, না দিলে সবচেয়ে ফাঁকা ব্লকে।
                    is_new_person = True
                    want_prov = _k(body.get("provider", ""))
                    pick, pick_free = None, -1
                    try:
                        _lidx = labor_index()
                    except Exception:
                        _lidx = {}
                    for b in blocks:
                        nc = b[0]
                        used = sum(1 for r in range(5, (ws.max_row or 0) + 1)
                                   if _nm(ws.cell(r, nc).value or ""))
                        prov_of = ""
                        for r in range(5, (ws.max_row or 0) + 1):
                            n2 = _nm(ws.cell(r, nc).value or "")
                            if n2 and not n2.lower().startswith(("total", "grand balance")):
                                prov_of = (_lidx.get(norm_person(n2)) or {}).get("provider", "")
                                if prov_of:
                                    break
                        if want_prov and _k(prov_of) == want_prov:
                            pick, pick_free = b, 0
                            break
                        if used < pick_free or pick is None:
                            pick, pick_free = b, used
                    found = (pick, None)
                (_nc, _ac, _dc, _sc, _rc), last = found
                import copy as _cp

                # সারি ঢোকানো/মুছে ফেলা যাবে না — এই শীটে মার্জড সেল আছে,
                # insert_rows দিলে পাশের প্রতিটি মানুষের লেখা হারিয়ে যায়।
                # তাই শুধু ওই ব্যক্তির নিজের ৫টি ঘরের পরের খালি সারি খুঁজে লেখা হয়।
                mrows = set()
                for _mr in ws.merged_cells.ranges:
                    for _rr in range(_mr.min_row, _mr.max_row + 1):
                        for _cc in range(_mr.min_col, _mr.max_col + 1):
                            if _nc <= _cc <= _rc:
                                mrows.add((_rr, _cc))
                style_row = last
                if last is None:
                    # নতুন মানুষ: এই ব্লকের প্রথম লেখা সারির ফরম্যাট নিয়ে নিই
                    style_row = None
                    for _r in range(5, (ws.max_row or 0) + 1):
                        if _nm(ws.cell(_r, _nc).value or ""):
                            style_row = _r
                            break
                    if style_row is None:
                        style_row = 5
                    tr = 5
                else:
                    tr = last + 1
                _lim = (ws.max_row or 0) + 60
                while tr <= _lim:
                    _empty = all(ws.cell(tr, _c).value in (None, "") for _c in range(_nc, _rc + 1))
                    if _empty and not any((tr, _c) in mrows for _c in range(_nc, _rc + 1)):
                        break
                    tr += 1
                else:
                    raise ValueError("এই মানুষের জন্য পরের খালি সারি পাওয়া যায়নি")

                maxc = ws.max_column or 76
                for _cc in range(1, maxc + 1):
                    try:
                        _s = ws.cell(style_row, _cc)
                        _d = ws.cell(tr, _cc)
                        _d.font = _cp.copy(_s.font)
                        _d.fill = _cp.copy(_s.fill)
                        _d.alignment = _cp.copy(_s.alignment)
                        _d.border = _cp.copy(_s.border)
                    except Exception:
                        pass

                maxc = ws.max_column or 76
                for _cc in range(1, maxc + 1):
                    try:
                        _s = ws.cell(style_row, _cc)
                        _d = ws.cell(tr, _cc)
                        _d.font = _cp.copy(_s.font)
                        _d.fill = _cp.copy(_s.fill)
                        _d.alignment = _cp.copy(_s.alignment)
                        _d.border = _cp.copy(_s.border)
                    except Exception:
                        pass
                if is_new_person and body.get("provider"):
                    _asg = assign_load()
                    _asg[person] = str(body.get("provider")).strip()
                    assign_save(_asg)
                ws.cell(tr, _nc).value = person
                ws.cell(tr, _ac).value = amt
                if date:
                    ws.cell(tr, _dc).value = date
                ws.cell(tr, _sc).value = "Paide" if paid else ""
                if reason:
                    ws.cell(tr, _rc).value = reason
                wb.save(fp)
                wb.close()
                if not restore_parts(fp):
                    shutil.copy2(bak, fp)
                    restore_parts(fp)
                    raise ValueError("ছবি/ইঙ্ক ফেরানো যায়নি — কোনো লেখা করা হয়নি")
                try:
                    verify_written(fp)
                    write_guard(fp, bak, before,
                                {(tr, _c) for _c in range(_nc, _rc + 1)})
                except Exception:
                    shutil.copy2(bak, fp)
                    restore_parts(fp)
                    raise
                self._json({"ok": True, "backup": bak,
                            "newPerson": is_new_person})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path in ("/api/ws/advance-paid", "/api/ws/advance-remove"):
            is_remove = (self.path == "/api/ws/advance-remove")
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                from openpyxl import load_workbook as _lw4
                fp = advance_ensure()
                if not os.path.isfile(fp):
                    raise FileNotFoundError(ADV_BOT + " নেই")
                person = " ".join(str(body.get("person", "")).split())
                idx = int(body.get("index", -1))
                amt = float(str(body.get("amount", "0")).replace(",", "").strip() or 0)

                def _k(s):
                    return re.sub(r"\s*\(.*", "", " ".join(str(s or "").split())).strip().lower()

                def _nm(v):
                    return " ".join(str(v or "").split())

                bak = backup_file(fp)
                before = cellsnap(fp)
                wb = _lw4(fp)
                ws = wb["Sheet1"]
                blocks = []
                for c in range(1, (ws.max_column or 0) + 1):
                    if _nm(ws.cell(4, c).value).lower() == "name":
                        blocks.append((c, c + 1, c + 2, c + 3, c + 4))
                want = _k(person)
                rows = []
                for b in blocks:
                    nc, ac, dc, sc, rc = b
                    for r in range(5, (ws.max_row or 0) + 1):
                        nm = _nm(ws.cell(r, nc).value)
                        if not nm:
                            continue
                        s = nm.lower()
                        if s.startswith("total") or s.startswith("grand balance"):
                            continue
                        if _k(nm) == want:
                            rows.append((r, sc))
                if idx < 0 or idx >= len(rows):
                    raise ValueError("এন্ট্রি পাইনি")
                r, sc = rows[idx]
                try:
                    cur_amt = float(str(ws.cell(r, sc - 2).value).replace(",", "").strip() or 0)
                except Exception:
                    cur_amt = 0
                if abs(cur_amt - amt) > 0.01:
                    raise ValueError("এন্ট্রি মিলছে না — রিলোড করে আবার চেষ্টা করুন")
                if is_remove:
                    # শুধু ওই ব্যক্তির নিজের ৫টি ঘর খালি করি।
                    # আগে ws.delete_rows(r) দিলে পুরো সারি মুছে যেত, ফলে পাশের
                    # প্রতিটি মানুষের ওই সারির লেখাও হারিয়ে যেত।
                    from openpyxl.cell.cell import MergedCell as _MC
                    nc = sc - 3
                    for c in range(nc, nc + 5):
                        cl = ws.cell(r, c)
                        if isinstance(cl, _MC):
                            continue
                        cl.value = None
                    allow = {(r, c) for c in range(nc, nc + 5)}
                else:
                    ws.cell(r, sc).value = "Paide"
                    allow = {(r, sc)}
                wb.save(fp)
                wb.close()
                try:
                    write_guard(fp, bak, before, allow)
                except Exception:
                    shutil.copy2(bak, fp)
                    restore_parts(fp)
                    raise
                self._json({"ok": True, "backup": bak, "removed": bool(is_remove)})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/backup-clean":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            try:
                days = int(body.get("days", 30))
                keep = int(body.get("keep", 10))
                if days < 1:
                    days = 30
                if keep < 1:
                    keep = 10
                import time as _tm
                cutoff = _tm.time() - days * 86400
                files = sorted(os.listdir(BACKUP_DIR))
                # always keep the newest `keep` files
                protected = set(files[-keep:] if len(files) > keep else files)
                removed, kept, freed = [], [], 0
                for fn in files:
                    p = os.path.join(BACKUP_DIR, fn)
                    if not os.path.isfile(p):
                        continue
                    if fn in protected or os.path.getmtime(p) >= cutoff:
                        kept.append(fn)
                        continue
                    try:
                        freed += os.path.getsize(p)
                        os.remove(p)
                        removed.append(fn)
                    except OSError:
                        kept.append(fn)
                self._json({"ok": True, "removed": removed, "removed_count": len(removed),
                            "kept_count": len(kept), "freed_bytes": freed})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 500)
            return
        if self.path == "/api/shutdown":
            # নিরাপদ বন্ধ: আগে রেসপন্স পাঠাও (ব্রাউজার "ok" পায়), তারপর
            # serve_forever লুপ নরমলি থামাও ও সকেট বন্ধ করো।
            # SIGTERM ব্যবহার করা হয় না — Windows-এ সেটা TerminateProcess,
            # অর্থাৎ হার্ড-কিল, যা লেখা চলা ফাইল ভেঙে দিতে পারে।
            # কোনো pending state নেই (মেমরি প্রতিটি POST-এ অ্যাটমিকভাবে ডিস্কে),
            # তাই শুধু সার্ভার বন্ধ করলেই যথেষ্ট।
            self._json({"ok": True, "message": "Server shutting down..."})
            srv = self.server
            import threading as _th

            def _graceful():
                time.sleep(0.8)                       # রেসপন্স ব্রাউজারে পৌঁছানোর সময়
                try:
                    srv.shutdown()                    # serve_forever লুপ থামে
                except Exception:
                    pass
                # server_close() কিছু ভার্সনে থ্রেড join করে — অনন্ত অপেক্ষা নয়
                done = _th.Event()

                def _close():
                    try:
                        srv.server_close()            # পোর্ট/সকেট ছাড়ে
                    except Exception:
                        pass
                    done.set()

                _th.Thread(target=_close, daemon=True).start()
                done.wait(1.5)                        # সর্বোচ্চ ১.৫ সেকেন্ড
                os._exit(0)                           # ডেমন থ্রেড আটকে যাওয়া এড়াতে

            _th.Timer(0.8, _graceful).start()
            return
        if self.path == "/api/restart":
            # 🔄 ফ্রেশ রিস্টার্ট: আগে রেসপন্স (ব্রাউজার "ok" পায়), তারপর নতুন
            # ইনস্ট্যান্স বসিয়ে দিয়ে বর্তমানটি নরমলি বেরিয়ে যায়।
            # SESSIONS মেমরিতে বসে — তাই রিস্টার্টের পর আবার লগইন লাগবে,
            # অর্থাৎ লক অটো-চালু থাকে (.users যাচাই করে lock_on())।
            # সকেট ছাড়ার আগেই নতুন প্রসেস তৈরি হয়, কিন্তু সেটি --wait দিয়ে
            # অপেক্ষা করে, তাই পোর্ট ৮৭৬৫-এ দুজনে ধাক্কা খায় না।
            self._json({"ok": True, "message": "Server restarting..."})
            import threading as _th

            def _restart():
                try:
                    _spawn_restart()                 # নতুন প্রসেস (চালু থাকবে, অপেক্ষায়)
                except Exception:
                    pass
                _graceful_stop(self.server, 0.6)     # তারপর এটি নরমলি বের

            _th.Timer(0.7, _restart).start()
            return
        # ---- extension routes (POST) ----
        if self.path in _EXT_POST:
            n = int(self.headers.get("Content-Length", 0))
            try:
                _b = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception:
                _b = {}
            try:
                _EXT_POST[self.path](self, self.path, _b)
            except Exception as _e:
                self._json({"ok": False, "error": str(_e)}, 500)
            return
        if self.path != "/api/generate":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        try:
            data = resolve_file(body.get("data", ""))
            tmpl = resolve_file(body.get("tmpl", ""))
            month = int(body.get("month", 9))
            year = int(body.get("year", 2026))
            warns = []
            try:
                info = analyze_data_sheet(data)
                warns = info["warnings"]
            except Exception:
                info = None
            # খালি Data ফাইল থেকে বানালে আগের ভালো আউটপুট নষ্ট হয় — ফেল-ক্লোজ
            if info is not None and not info.get("workers"):
                raise ValueError("Data ফাইলে কোনো লোক নেই — Generate বাতিল। Generate সেকশনের Data ফাইলে সঠিক ফাইল বেছে নিন")
            bak = backup_file(data)  # backup BEFORE work, always (টগল বন্ধ)
            out_name = "Total T sheet AUTO {0:02d}-{1} বট.xlsx".format(month, year)
            out_path = os.path.join(OUT_DIR, out_name)
            out_bak = backup_file(out_path) if os.path.isfile(out_path) else None  # আগের আউটপুটেরও ব্যাকআপ
            # pass site rates from profit_srates.json
            _srates = srates_load()
            _duty = duty_load()
            res = generate_total_sheet(data, tmpl, out_path, month, year, _srates, _duty)
            try:
                verify_written(out_path)
            except Exception:
                roll_back(out_path, out_bak, out_bak is not None)
                raise
            self._json({"ok": True, "output": out_name, "backup": bak,
                        "output_backup": out_bak, "warnings": warns,
                        **{k: v for k, v in res.items() if k != "output"}})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)


def ensure_packages():
    """Auto-install missing pip packages from requirements.txt at boot."""
    try:
        req = os.path.join(BASE, "requirements.txt")
        if not os.path.isfile(req):
            return {"ok": True, "installed": []}
        import subprocess as _sp, sys as _sys
        import importlib.util as _ilu
        missing = []
        for line in open(req, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = __import__("re").split(r"[<>=!~\s\[]", line)[0].strip().lower().replace("-", "_")
            if _ilu.find_spec(name) is None:
                missing.append(line)
        if not missing:
            return {"ok": True, "installed": []}
        print("Installing missing packages:", ", ".join(missing))
        _sp.run([_sys.executable, "-m", "pip", "install", "--quiet"] + missing,
                timeout=600, capture_output=True)
        still = [m for m in missing
                 if _ilu.find_spec(__import__("re").split(r"[<>=!~\s\[]", m)[0].strip().lower().replace("-", "_")) is None]
        return {"ok": not still, "installed": missing, "failed": still}
    except Exception as e:
        print("Auto-install skipped:", e)
        return {"ok": False, "error": str(e)}


def _graceful_stop(srv, delay=0.8):
    """সার্ভার নরমলি বন্ধ: রেসপন্স পৌঁছানো → serve_forever থামে → সকেট ছাড়ে।
    SIGTERM ব্যবহার করা হয় না — Windows-এ সেটা হার্ড-কিল, যা লেখা চলা ফাইল
    ভঙ্গ করতে পারে। কোনো pending state নেই (সব POST-ই অ্যাটমিক ডিস্কে),
    তাই সকেট বন্ধ করলেই যথেষ্ট।"""
    import threading as _th
    time.sleep(delay)                           # রেসপন্স ব্রাউজারে পৌঁছানোর সময়
    try:
        srv.shutdown()                          # serve_forever লুপ থামে
    except Exception:
        pass
    done = _th.Event()

    def _close():
        try:
            srv.server_close()                  # পোর্ট/সকেট ছাড়ে
        except Exception:
            pass
        done.set()

    _th.Thread(target=_close, daemon=True).start()
    done.wait(1.5)                              # সর্বোচ্চ ১.৫ সেকেন্ড
    os._exit(0)                                 # ডেমন থ্রেড আটকে যাওয়া এড়াতে


def _spawn_restart():
    """🔄 ফ্রেশ ইনস্ট্যান্স চালু করো — উইন্ডো ছাড়া, ডিটাচড, লগ ফাইলসহ।
    নতুন প্রসেস --wait=N দিয়ে শুরু হয়, যাতে পুরনোটি পোর্ট ৮৭৬৫ ছাড়ার
    আগে তা ধরতে না চেষ্টা করে। লগ restart.log-এ যায়।"""
    import subprocess as _sp
    py = os.path.abspath(sys.executable)        # যেই পাইথনে openpyxl আছে
    script = os.path.abspath(__file__)          # D:\ai manager\app.py
    wait_s = 4                                  # পুরনো সকেট ছাড়ার নিরাপদ অপেক্ষা
    _DETACHED = getattr(_sp, "DETACHED_PROCESS", 0x00000008)
    _NEWGRP = getattr(_sp, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    try:
        log = open(os.path.join(BASE, "restart.log"), "ab")
    except Exception:
        log = open(os.devnull, "wb")
    try:
        _sp.Popen([py, "-u", script, "--wait={0}".format(wait_s)],   # -u → লগ ব্লক-বাফার নয়, সাথে সাথে লেখা হয়
                  cwd=BASE,
                  stdin=_sp.DEVNULL, stdout=log, stderr=_sp.STDOUT,
                  creationflags=_DETACHED | _NEWGRP)
    finally:
        try:
            log.close()
        except Exception:
            pass


def setup_status():
    import importlib.util as _ilu, shutil as _sh
    pkgs = {}
    try:
        for line in open(os.path.join(BASE, "requirements.txt"), encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = __import__("re").split(r"[<>=!~\s\[]", line)[0].strip()
            key = name.lower().replace("-", "_")
            pkgs[name] = _ilu.find_spec(key) is not None
    except Exception:
        pass
    return {"packages": pkgs,
            "tesseract": _sh.which("tesseract") is not None,
            "drive_ok": os.path.isdir(DRIVE_DIR),
            "ocr_dir": os.path.isdir(OCR_DIR),
            "drivers": sorted(os.listdir(os.path.join(BASE, "drivers")))
            if os.path.isdir(os.path.join(BASE, "drivers")) else []}


def main():
    port = 8765
    # 🔄 রিস্টার্ট থেকে ফিরে আসা প্রসেস: আগে অপেক্ষা, যাতে পুরনো সকেট
    # সম্পূর্ণ ছাড়ে — তারপর বাইন্ডিং শুরু (পোর্ট ধাক্কা এড়াতে)।
    for _a in sys.argv[1:]:
        if _a.startswith("--wait="):
            try:
                _w = float(_a.split("=", 1)[1])
            except Exception:
                _w = 0.0
            if _w > 0:
                print("Restart wait: {0:g}s ...".format(_w))
                time.sleep(_w)
            break
    try:
        r = ensure_packages()
        if not r.get("ok"):
            print("Setup warning:", r)
    except Exception as e:
        print("Setup warning:", e)
    try:
        n = trash_purge()
        if n:
            print(f"Trash auto-cleaned: {n} item(s) older than {TRASH_DAYS} days")
    except Exception as e:
        print("Trash auto-clean skipped:", e)
    print(f"AI Time Keeper running: http://127.0.0.1:{port}")
    load_extensions()
    if "--open" in sys.argv:
        try:
            import threading as _th
            import webbrowser as _wb
            _th.Timer(1.0, lambda: _wb.open(f"http://127.0.0.1:{port}")).start()
            print("Opening dashboard in your default browser...")
        except Exception as e:
            print("Auto-open skipped:", e)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
