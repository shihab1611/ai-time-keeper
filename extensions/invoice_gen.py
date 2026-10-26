# -*- coding: utf-8 -*-
"""Provider Invoice Generator extension.

Data Sheet (hours/rates/gas) + Advance Sheet (advance) থেকে প্রতি
প্রোভাইডারের জন্য প্রিন্ট-রেডি ইনভয়েস বানায়।
Time Keeper ইঞ্জিনে (app.py/generator.py) কোনো পরিবর্তন ছাড়াই চলে।
"""
import os
import re
import json
import time
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(BASE, "input output")
CFG_FILE = os.path.join(BASE, "extensions", "invoice_config.json")
BACKUP_DIR = os.path.join(BASE, "backup")

DRIVE_DIR = r"C:\Users\Admin\OneDrive\Desktop\somuj vai"
ADV_DIR = os.path.join(DRIVE_DIR, "All Advance Sheets")
ADV_FILE = os.path.join(ADV_DIR, "Advance sheet বট.xlsx")

# Data-sheet worker name -> advance-sheet name (hand-confirmed aliases)
ALIASES = {
    "shamsuddin": "shamsudhuha",
    "md shihab": "shihab",
    "abdirehman arega yasin": "abdirehman",
    "seyfu jundi adem": "seyfu",
    "aimable igiraneza": "aimable",
    "patrick gatoto": "patrick",
    "juma mwalimu swaleh": "juma",
    "oscar niyoyabishatse": "oscar",
}

MONTHS = {
    1: "JANUARY", 2: "FEBRUARY", 3: "MARCH", 4: "APRIL",
    5: "MAY", 6: "JUNE", 7: "JULY", 8: "AUGUST",
    9: "SEPTEMBER", 10: "OCTOBER", 11: "NOVEMBER", 12: "DECEMBER",
}


# ---------------------------------------------------------------- helpers
def norm_person(s):
    s = re.sub(r"\s*\(.*", "", str(s or "")).strip().lower()
    return " ".join(s.split())


def first_last(n):
    parts = norm_person(n).split()
    return (parts[0], parts[-1]) if parts else ("", "")


def _num(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    try:
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _nm(v):
    return " ".join(str(v or "").split())


def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"settings": {}, "company": {}, "providers": {}}


def save_cfg(cfg):
    if os.path.isfile(CFG_FILE):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            shutil.copy2(CFG_FILE, os.path.join(BACKUP_DIR, "INVCFG." + ts + ".json"))
        except Exception:
            pass
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- data readers
def find_data_sheet(month=None, year=None, source="current"):
    """Data sheet ফাইল খুঁজে বের করে। source='archive' হলে মাস ফোল্ডার থেকে নেয়।"""
    if source == "archive" and month and year:
        label = "%s-%d" % (MONTHS.get(int(month), "JAN")[:3], int(year))
        base = os.path.join(BASE, "months", label)
        for sub in ("data sheet and total time sheet", ""):
            d = os.path.join(base, sub) if sub else base
            if os.path.isdir(d):
                c = [os.path.join(d, f) for f in os.listdir(d)
                     if f.lower().endswith((".xlsx", ".xlsm")) and "data sheet" in f.lower()]
                if c:
                    c.sort(key=os.path.getmtime, reverse=True)
                    return c[0]
    cand = []
    if os.path.isdir(INPUT_DIR):
        for fn in os.listdir(INPUT_DIR):
            if fn.lower().endswith((".xlsx", ".xlsm")) and "data sheet" in fn.lower():
                cand.append(os.path.join(INPUT_DIR, fn))
    if not cand:
        return None
    if month:
        m_abbr = (MONTHS.get(int(month), "")[:3]).lower()
        matched = [p for p in cand if m_abbr in os.path.basename(p).lower()]
        if matched:
            matched.sort(key=os.path.getmtime, reverse=True)
            return matched[0]
    cand.sort(key=os.path.getmtime, reverse=True)
    return cand[0]


def data_month_year():
    """ডাটা শিটের A1 তারিখ থেকে (month, year); না পেলে আজকের মাস।"""
    from openpyxl import load_workbook
    from datetime import datetime
    fp = find_data_sheet()
    if fp:
        try:
            wb = load_workbook(fp, data_only=True)
            ws = wb[wb.sheetnames[0]]
            for r in range(1, 6):
                for c in range(1, 6):
                    v = ws.cell(r, c).value
                    if isinstance(v, datetime):
                        wb.close()
                        return v.month, v.year
            wb.close()
        except Exception:
            pass
    now = time.localtime()
    return now.tm_mon, now.tm_year


def _day_hours(v):
    """দিনের ঘরের মান -> ঘণ্টা (A/S/খালি = 0), ইঞ্জিনের to_hours-এর মতো।"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    if s.upper() in ("A", "S", "OFF", "H", "W", "L", "X", "NIL", "-"):
        return 0.0
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def read_data_sheet(fp=None, month=None, year=None, source="current"):
    """Data sheet থেকে provider -> [{name,hours,rate,gas}] এবং gas সারাংশ। source='archive' হলে মাস ফোল্ডার থেকে নেয়।"""
    from openpyxl import load_workbook
    if not fp:
        fp = find_data_sheet(month=month, year=year, source=source)
    if not fp:
        raise FileNotFoundError("Data sheet পাওয়া যায়নি (input output ফোল্ডার)")
    wb = load_workbook(fp, data_only=True)
    ws = wb[wb.sheetnames[0]]
    prov_workers = {}
    order = []
    cur = None
    for r in range(3, (ws.max_row or 0) + 1):
        prov = ws.cell(r, 2).value
        name = ws.cell(r, 3).value
        if prov and str(prov).strip() not in ("Provider", "None", ""):
            cur = str(prov).strip()
        if not name:
            continue
        # hours: দিনের ঘর (col 4-34) থেকে যোগ — "Total Duty hour" ঘর খালি থাকলেও চলে
        hrs = round(sum(_day_hours(ws.cell(r, c).value) for c in range(4, 35)), 2)
        if not hrs:
            hrs = _num(ws.cell(r, 35).value)
        rate = _num(ws.cell(r, 36).value)
        gas = _num(ws.cell(r, 39).value)
        if cur not in prov_workers:
            prov_workers[cur] = []
            order.append(cur)
        prov_workers[cur].append({
            "name": str(name).strip(), "hours": hrs, "rate": rate, "gas": gas,
        })
    wb.close()
    return fp, prov_workers, order


def read_advance():
    """Advance bot copy থেকে norm-key -> {name,total,paid,balance}।"""
    from openpyxl import load_workbook
    fp = ADV_FILE
    if not os.path.isfile(fp):
        master = os.path.join(ADV_DIR, "Advance sheet.xlsx")
        if os.path.isfile(master):
            fp = master
        else:
            return {}, []
    wb = load_workbook(fp, data_only=True)
    ws = wb["Sheet1"]
    people = {}
    order = []
    blocks = []
    for c in range(1, (ws.max_column or 0) + 1):
        if _nm(ws.cell(4, c).value).lower() == "name":
            blocks.append((c, c + 1, c + 2, c + 3, c + 4))
    if not blocks:
        blocks = [(6, 7, 8, 9, 10)]

    def _cleared(st):
        s = st.lower()
        return ("paid" in s) or ("clear" in s)

    for _nc, _ac, _dc, _sc, _rc in blocks:
        for r in range(5, (ws.max_row or 0) + 1):
            name = _nm(ws.cell(r, _nc).value)
            if not name:
                continue
            low = name.lower()
            if low.startswith("total") or low.startswith("grand balance"):
                continue
            key = norm_person(name)
            if not key:
                continue
            if key not in people:
                people[key] = {"name": re.sub(r"\s*\(.*", "", name).strip(),
                               "total": 0.0, "paid": 0.0, "balance": 0.0}
                order.append(key)
            amt = _num(ws.cell(r, _ac).value)
            st = _nm(ws.cell(r, _sc).value)
            people[key]["total"] += amt
            if _cleared(st):
                people[key]["paid"] += amt
            else:
                people[key]["balance"] += amt
    wb.close()
    return people, order


def match_advance(ds_name, people):
    n = norm_person(ds_name)
    if n in ALIASES and ALIASES[n] in people:
        return people[ALIASES[n]]
    if n in people:
        return people[n]
    fl = first_last(ds_name)
    if fl != ("", ""):
        for k, v in people.items():
            if first_last(k) == fl:
                return v
    for k, v in people.items():
        if k and (n in k or k in n):
            return v
    return None


# ---------------------------------------------------------------- number to words
ONES = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT",
        "NINE", "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN",
        "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
TENS = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY",
        "EIGHTY", "NINETY"]


def _under1000(n):
    out = []
    if n >= 100:
        out.append(ONES[n // 100] + " HUNDRED")
        n %= 100
    if n >= 20:
        t = TENS[n // 10]
        if n % 10:
            t += "-" + ONES[n % 10]
        out.append(t)
    elif n > 0:
        out.append(ONES[n])
    return " ".join(out)


def amount_words(x):
    n = int(round(x))
    if n == 0:
        return "ZERO"
    parts = []
    for div, label in ((1000000, "MILLION"), (1000, "THOUSAND")):
        if n >= div:
            parts.append(_under1000(n // div) + " " + label)
            n %= div
    if n:
        parts.append(_under1000(n))
    return " ".join(parts)


# ---------------------------------------------------------------- invoice builder
def build_invoice(prov_key, month=None, year=None, rates=None, adv=None, gas=None,
                  client=None, address=None):
    """rates: {worker_name: new_rate}; adv/gas: manual totals (None=auto)।
    client/address: স্টেটমেন্টের PAY TO — UI থেকে এডিট করা ভ্যালু (None=ডিফল্ট)।"""
    cfg = load_cfg()
    settings = cfg.get("settings", {})
    company = cfg.get("company", {})
    prov_cfg = cfg.get("providers", {}).get(prov_key, {})

    # default month = data sheet's own month (A1 date), not today
    dm, dy = data_month_year()
    now = time.localtime()
    m = int(month) if month else dm
    y = int(year) if year else dy
    date_s = "%02d %s %d" % (now.tm_mday, MONTHS.get(now.tm_mon, ""), now.tm_year)

    ds_path, prov_workers, prov_order = read_data_sheet(month=m, year=y)
    # archive fallback: লাইভ শিটে দিনের ঘর খালি হলে মাস ফোল্ডার থেকে পড়া
    if prov_workers and all(sum(w["hours"] for w in ws_list) == 0 for ws_list in prov_workers.values()):
        arc_path, arc_workers, arc_order = read_data_sheet(month=m, year=y, source="archive")
        if arc_workers:
            ds_path, prov_workers, prov_order = arc_path, arc_workers, arc_order
    # provider key normalization: match config keys to data-sheet names
    ds_name = None
    for pn in prov_order:
        if norm_person(pn) == norm_person(prov_cfg.get("display", prov_key)):
            ds_name = pn
            break
        if prov_key.replace("mr.", "") in norm_person(pn):
            ds_name = pn
            break
    if ds_name is None:
        # try display name containing
        for pn in prov_order:
            d = norm_person(prov_cfg.get("display", ""))
            if d and d in norm_person(pn):
                ds_name = pn
                break
    if ds_name is None:
        raise ValueError("Data sheet-এ এই প্রোভাইডারের নাম পাওয়া যায়নি: " + str(prov_key))

    workers_raw = prov_workers.get(ds_name, [])
    people, _ = read_advance()
    adv_src = settings.get("advance_source", "balance")

    workers = []
    total_amt = 0.0
    gas_sum = 0.0
    adv_sum = 0.0
    for i, w in enumerate(workers_raw, 1):
        rate = w["rate"]
        if rates and w["name"] in rates:
            try:
                rate = float(rates[w["name"]])
            except (TypeError, ValueError):
                pass
        amt = w["hours"] * rate
        total_amt += amt
        gas_sum += w["gas"]
        hit = match_advance(w["name"], people)
        wadv = 0.0
        if hit:
            wadv = hit.get(adv_src, 0.0) or 0.0
        adv_sum += wadv
        workers.append({
            "sl": i, "name": w["name"], "hours": w["hours"], "rate": rate,
            "amount": amt, "advance": wadv,
        })

    # manual overrides (user-typed)
    if gas is not None:
        try:
            gas_sum = float(gas)
        except (TypeError, ValueError):
            pass
    if adv is not None:
        try:
            adv_sum = float(adv)
        except (TypeError, ValueError):
            pass

    net = total_amt - gas_sum - adv_sum

    # statement number: assign once per provider+month, reuse on re-preview
    assigned_map = settings.get("assigned", {}) if isinstance(settings.get("assigned"), dict) else {}
    skey = "%s|%s|%s" % (prov_key, m, y)
    if skey in assigned_map:
        inv_no = int(assigned_map[skey])
    else:
        inv_no = int(settings.get("invoice_start_no", 1))
        assigned_map[skey] = inv_no
        cfg.setdefault("settings", {})["assigned"] = assigned_map
        cfg["settings"]["invoice_start_no"] = inv_no + 1
        save_cfg(cfg)
    inv_no_s = "%02d" % inv_no

    return {
        "ok": True,
        "invoice_no": inv_no_s,
        "date": date_s,
        "month_name": MONTHS.get(m, ""),
        "year": y,
        "client": (str(client).strip() if client and str(client).strip()
                   else settings.get("payto_client") or prov_cfg.get("client", "")),
        "address": (str(address).strip() if address and str(address).strip()
                    else settings.get("payto_address") or prov_cfg.get("address", "")),
        "company": company,
        "workers": workers,
        "total": round(total_amt, 2),
        "gas": round(gas_sum, 2),
        "advance": round(adv_sum, 2),
        "advance_source": adv_src,
        "net": round(net, 2),
        "in_words": amount_words(net),
        "prov_key": prov_key,
        "prov_display": prov_cfg.get("display", prov_key),
        "from_name": prov_cfg.get("from_name") or prov_cfg.get("display", prov_key),
    }


# ---------------------------------------------------------------- PDF generation
# professional navy theme
NAVY = (31, 56, 100)
NAVY_LT = (224, 231, 242)
ZEBRA = (244, 247, 251)
BORDER = (201, 209, 222)
GRAY = (110, 110, 110)
DARK = (25, 25, 25)
WHITE = (255, 255, 255)


def make_pdf(data, out_path, kind="statement"):
    """Payment Statement / Company Invoice PDF — fpdf2, navy theme (English only)."""
    from fpdf import FPDF
    is_inv = (kind == "invoice")
    doc_ttl = "COMPANY INVOICE" if is_inv else "PAYMENT STATEMENT"
    no_lbl = "INVOICE NO" if is_inv else "STATEMENT NO"
    PW, PH = 210.0, 297.0
    LM = 12.0
    W = PW - 2 * LM          # 186 content width

    def money(x):
        return "{:,.2f}".format(float(x or 0))

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(left=LM, top=12, right=LM)
    pdf.add_page()

    # ---------------- header band (full bleed) ----------------
    band_h = 27.0
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, PW, band_h, style="F")
    cx, cy, cr = LM + 8.0, band_h / 2.0, 8.0
    pdf.set_fill_color(*WHITE)
    pdf.circle(cx, cy, cr, style="F")
    pdf.set_text_color(*NAVY)
    pdf.set_font("helvetica", "B", 13)
    pdf.set_xy(cx - cr, cy - 4.5)
    pdf.cell(cr * 2, 9, "MM", align="C")
    tx = cx + cr + 5.0
    pdf.set_text_color(*WHITE)
    pdf.set_font("helvetica", "B", 15)
    pdf.set_xy(tx, 6.5)
    pdf.cell(W, 8, data["company"].get("name", ""), align="L")
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(206, 216, 232)
    pdf.set_xy(tx, 15.5)
    pdf.cell(W, 6, "PHONE: %s    |    EMAIL: %s" % (
        data["company"].get("contact", ""), data["company"].get("email", "")), align="L")

    # ---------------- title ----------------
    y = band_h + 6.0
    pdf.set_text_color(*NAVY)
    pdf.set_font("helvetica", "B", 13)
    pdf.set_xy(LM, y)
    pdf.cell(W, 7, doc_ttl, align="C")
    rule_w = 60.0
    rx = LM + (W - rule_w) / 2.0
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.7)
    pdf.line(rx, y + 8.0, rx + rule_w, y + 8.0)
    pdf.set_line_width(0.2)

    # ---------------- meta row ----------------
    y += 12.0
    pdf.set_text_color(*DARK)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_xy(LM, y)
    pdf.cell(W * 0.5, 6, "%s: %s" % (no_lbl, data["invoice_no"]), align="L")
    pdf.set_xy(LM + W * 0.5, y)
    pdf.cell(W * 0.5, 6, "Date: %s" % data["date"], align="R")

    # ---------------- bill to / from ----------------
    y += 9.0
    colL = LM
    colR = LM + W * 0.58
    to_lbl = "BILL TO" if is_inv else "PAY TO"
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(*NAVY)
    pdf.set_xy(colL, y)
    pdf.cell(W * 0.55, 5, to_lbl, align="L")
    pdf.set_xy(colR, y)
    pdf.cell(W * 0.42, 5, "FROM", align="L")
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*DARK)
    pdf.set_xy(colL, y + 5.5)
    pdf.cell(W * 0.55, 6, "%s," % data["client"], align="L")
    pdf.set_xy(colR, y + 5.5)
    pdf.cell(W * 0.42, 6, data.get("from_name", ""), align="L")
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(colL, y + 11.0)
    pdf.cell(W * 0.55, 5, data.get("address", ""), align="L")

    # ---------------- month pill ----------------
    y += 18.0
    pill_pref = "INVOICE" if is_inv else "PAYMENT"
    pill = "%s FOR THE MONTH OF %s - %s" % (pill_pref, data["month_name"], data["year"])
    pdf.set_font("helvetica", "B", 9.5)
    pw_ = pdf.get_string_width(pill) + 8.0
    pdf.set_fill_color(*NAVY_LT)
    pdf.set_draw_color(*NAVY)
    pdf.rect(LM, y, pw_, 7.5, style="DF")
    pdf.set_text_color(*NAVY)
    pdf.set_xy(LM, y)
    pdf.cell(pw_, 7.5, pill, align="C")

    # ---------------- table ----------------
    y += 13.0
    colw = [W * 0.08, W * 0.33, W * 0.15, W * 0.14, W * 0.15, W * 0.15]
    last_col = "Total Amount In AED" if is_inv else "Net Amount In AED"
    heads = ["SL No", "NAME", "No. of Hours", "Unit Price", "Amount", last_col]
    colx = [LM]
    for cw in colw[:-1]:
        colx.append(colx[-1] + cw)
    TW = sum(colw)
    headh, rowh = 8.0, 6.4
    pdf.set_fill_color(*NAVY)
    pdf.rect(LM, y, TW, headh, style="F")
    pdf.set_text_color(*WHITE)
    pdf.set_font("helvetica", "B", 8.5)
    for i, h in enumerate(heads):
        pdf.set_xy(colx[i], y)
        pdf.cell(colw[i], headh, h, align="C")
    ry = y + headh
    for idx, wkr in enumerate(data["workers"]):
        if idx % 2 == 1:
            pdf.set_fill_color(*ZEBRA)
            pdf.rect(LM, ry, TW, rowh, style="F")
        pdf.set_text_color(*DARK)
        pdf.set_font("helvetica", "", 9)
        nm = str(wkr["name"])[:34]
        pdf.set_xy(colx[0], ry)
        pdf.cell(colw[0], rowh, str(wkr["sl"]), align="C")
        pdf.set_xy(colx[1] + 2, ry)
        pdf.cell(colw[1] - 2, rowh, nm, align="L")
        vals = ["{:.2f}".format(wkr["hours"]), "{:.2f}".format(wkr["rate"]),
                money(wkr["amount"]), money(wkr["amount"])]
        for i, v in enumerate(vals, start=2):
            pdf.set_xy(colx[i], ry)
            pdf.cell(colw[i] - 2, rowh, v, align="R")
        ry += rowh
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(LM, y, TW, ry - y)
    for cx2 in colx[1:]:
        pdf.line(cx2, y + headh, cx2, ry)
    pdf.line(LM, y + headh, LM + TW, y + headh)
    for k in range(1, len(data["workers"]) + 1):
        yy = y + headh + rowh * k
        pdf.line(LM, yy, LM + TW, yy)

    # ---------------- totals ----------------
    ry += 4.0
    sumw = 82.0
    x0 = LM + W - sumw
    plain = [("TOTAL", money(data["total"]) + " AED")]
    if not is_inv:
        plain += [("GAS", money(data["gas"]) + " AED"),
                  ("ADVANCE", money(data["advance"]) + " AED")]
    pdf.set_font("helvetica", "", 10)
    for lbl, val in plain:
        pdf.set_text_color(*GRAY)
        pdf.set_xy(x0, ry)
        pdf.cell(sumw * 0.55, 6, lbl, align="L")
        pdf.set_text_color(*DARK)
        pdf.set_xy(x0 + sumw * 0.55, ry)
        pdf.cell(sumw * 0.45, 6, val, align="R")
        ry += 6.0
    ry += 1.0
    pdf.set_fill_color(*NAVY)
    pdf.rect(x0, ry, sumw, 9.0, style="F")
    pdf.set_text_color(*WHITE)
    pdf.set_font("helvetica", "B", 11)
    net_lbl = "TOTAL PAYABLE AMOUNT" if is_inv else "NET PAYABLE AMOUNT"
    pdf.set_xy(x0 + 3, ry)
    pdf.cell(sumw * 0.55, 9, net_lbl, align="L")
    pdf.set_xy(x0 + sumw * 0.55 - 3, ry)
    pdf.cell(sumw * 0.45, 9, money(data["net"]) + " AED", align="R")
    ry += 9.0

    # ---------------- in words box ----------------
    ry += 5.0
    boxh = 10.0
    pdf.set_fill_color(*NAVY_LT)
    pdf.rect(LM, ry, W, boxh, style="F")
    pdf.set_fill_color(*NAVY)
    pdf.rect(LM, ry, 1.6, boxh, style="F")
    pdf.set_text_color(*NAVY)
    pdf.set_font("helvetica", "BI", 10)
    pdf.set_xy(LM + 4, ry)
    pdf.cell(W - 6, boxh, "In words: (%s AED & FIFTY-FILLS)" % data["in_words"], align="L")
    ry += boxh

    # ---------------- thank you + signature box ----------------
    ry += 12.0
    pdf.set_text_color(*DARK)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_xy(LM, ry)
    pdf.cell(W * 0.5, 6, "Thank You", align="L")
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(LM, ry + 7)
    pdf.cell(W * 0.5, 5, "For queries contact: %s" % data["company"].get("email", ""), align="L")
    sbw, sbh = 58.0, 24.0
    sbx = LM + W - sbw
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.4)
    pdf.rect(sbx, ry - 2, sbw, sbh)
    pdf.set_line_width(0.2)
    pdf.line(sbx + 6, ry + sbh - 8, sbx + sbw - 6, ry + sbh - 8)
    pdf.set_text_color(*GRAY)
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_xy(sbx, ry + sbh - 7)
    pdf.cell(sbw, 5, "Authorised Signatory", align="C")

    # ---------------- footer bar ----------------
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, PH - 11, PW, 11, style="F")
    pdf.set_text_color(*WHITE)
    pdf.set_font("helvetica", "", 8)
    pdf.set_xy(0, PH - 11)
    pdf.cell(PW, 11, "%s  ·  %s  ·  Computer generated document"
             % (data["company"].get("name", ""), doc_ttl), align="C")

    pdf.output(out_path)
    return out_path


def _safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(s)).strip("-")


def _ensure_month_tree(month, year):
    """মাস ফোল্ডারে ৩টা সাব-ফোল্ডার তৈরি + শিটগুলো ভেতরে সরায়।"""
    mdir = os.path.join(BASE, "months", "%s-%d" % (MONTHS.get(month, "???")[:3], year))
    subs = ["data sheet and total time sheet", "statements", "invoice"]
    for s in subs:
        os.makedirs(os.path.join(mdir, s), exist_ok=True)
    # loose sheets/json at month root -> move into data-sheet subfolder
    dsub = os.path.join(mdir, subs[0])
    moved = []
    try:
        for fn in os.listdir(mdir):
            fp = os.path.join(mdir, fn)
            if not os.path.isfile(fp):
                continue
            low = fn.lower()
            if low.endswith((".xlsx", ".xlsm")) or low.endswith((".json", ".txt")):
                dst = os.path.join(dsub, fn)
                if not os.path.exists(dst):
                    shutil.move(fp, dst)
                    moved.append(fn)
    except OSError:
        pass
    return mdir, moved


def api_save_statements(handler, path, body):
    """Month Clear-এ কল হয় — মাসের সব পেমেন্ট স্টেটমেন্ট PDF হয়ে সেভ।"""
    try:
        month = int(body.get("month") or 0)
        year = int(body.get("year") or 0)
        if not (month and year):
            now = time.localtime()
            month, year = now.tm_mon, now.tm_year
        mdir, moved = _ensure_month_tree(month, year)
        cfg = load_cfg()
        prov_cfg_all = cfg.get("providers", {})
        # unique display names (avoid duplicate keys for somuj aliases)
        ds_path, prov_workers, prov_order = read_data_sheet(month=month, year=year)
        # archive fallback: লাইভ শিটে দিনের ঘর খালি হলে মাস ফোল্ডার থেকে পড়া
        if prov_workers and all(sum(w["hours"] for w in ws_list) == 0
                                for ws_list in prov_workers.values()):
            arc_path, arc_workers, arc_order = read_data_sheet(month=month, year=year,
                                                               source="archive")
            if arc_workers:
                ds_path, prov_workers, prov_order = arc_path, arc_workers, arc_order
        done = []
        errors = []
        out_dir = os.path.join(mdir, "statements")
        os.makedirs(out_dir, exist_ok=True)
        seen = set()
        for pn in prov_order:
            # resolve config key for this data-sheet provider
            key = None
            for k, v in prov_cfg_all.items():
                d = norm_person(v.get("display", ""))
                if d and d in norm_person(pn):
                    key = k
                    break
            if key is None:
                key = norm_person(pn).replace(" ", ".")
            if key in seen:
                continue
            seen.add(key)
            try:
                data = build_invoice(key, month, year)
                fname = "%02d-%s.pdf" % (int(data["invoice_no"]), _safe_name(data["prov_display"]))
                outp = os.path.join(out_dir, fname)
                make_pdf(data, outp)
                if os.path.isfile(outp) and os.path.getsize(outp) > 0:
                    done.append(fname)
                else:
                    errors.append(key + ": ফাইল তৈরি হয়নি")
            except Exception as e:
                errors.append("%s: %s" % (key, e))
        handler._json({"ok": True, "dir": out_dir, "saved": done,
                       "count": len(done), "errors": errors, "moved": moved})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def _month_dir(month, year):
    return os.path.join(BASE, "months", "%s-%d" % (MONTHS.get(int(month), "JAN")[:3], int(year)))


def api_save_one(handler, path, body):
    """প্রিভিউ থেকে [সেভ] চাপলে — এক প্রোভাইডারের স্টেটমেন্ট PDF সেভ।"""
    try:
        prov = str(body.get("prov", "") or "").strip()
        if not prov:
            handler._json({"ok": False, "error": "প্রোভাইডার সিলেক্ট করুন"}, 400)
            return
        month = int(body.get("month") or 0) or None
        year = int(body.get("year") or 0) or None
        rates = body.get("rates") if isinstance(body.get("rates"), dict) else None
        adv = body.get("adv")
        gas = body.get("gas")
        data = build_invoice(prov, month, year, rates=rates, adv=adv, gas=gas,
                             client=body.get("client"), address=body.get("address"))
        mnum = [k for k, v in MONTHS.items() if v == data["month_name"]]
        out_dir = os.path.join(_month_dir(mnum[0] if mnum else 1, data["year"]),
                              "statements")
        os.makedirs(out_dir, exist_ok=True)
        fname = "%s-%s.pdf" % (data["invoice_no"], _safe_name(data["prov_display"]))
        outp = os.path.join(out_dir, fname)
        make_pdf(data, outp)
        handler._json({"ok": True, "file": fname, "dir": out_dir,
                       "invoice_no": data["invoice_no"]})
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


# ---------------------------------------------------------------- routes
def _q1(q, k, d=""):
    """parse_qs লিস্ট দেয় — প্রথম ভ্যালু বের করে।"""
    v = q.get(k, d)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else d
    return v


def api_build(handler, path, q):
    try:
        prov = str(_q1(q, "prov", "") or "").strip()
        if not prov:
            handler._json({"ok": False, "error": "প্রোভাইডার সিলেক্ট করুন"}, 400)
            return
        month = _q1(q, "month", "") or None
        year = _q1(q, "year", "") or None
        # manual edits from preview UI
        adv = _q1(q, "adv", "")
        gas = _q1(q, "gas", "")
        rates = {}
        raw_rates = str(_q1(q, "rates", "") or "")
        if raw_rates:
            try:
                parsed = json.loads(raw_rates)
                if isinstance(parsed, dict):
                    rates = parsed
            except ValueError:
                rates = {}
        data = build_invoice(prov, month, year,
                             rates=rates or None,
                             adv=(adv if str(adv).strip() != "" else None),
                             gas=(gas if str(gas).strip() != "" else None),
                             client=_q1(q, "client", "") or None,
                             address=_q1(q, "address", "") or None)
        handler._json(data)
    except Exception as e:
        handler._json({"ok": False, "error": str(e)}, 500)


def api_providers(handler, path, q):
    cfg = load_cfg()
    ds_path, prov_workers, prov_order = read_data_sheet()
    dm, dy = data_month_year()
    out = []
    for pn in prov_order:
        # find a config key whose display matches this data-sheet provider
        key = None
        for k, v in cfg.get("providers", {}).items():
            d = norm_person(v.get("display", ""))
            if d and d in norm_person(pn):
                key = k
                break
        if key is None:
            key = norm_person(pn).replace(" ", ".")
        out.append({"key": key, "data_name": pn,
                    "display": cfg.get("providers", {}).get(key, {}).get("display", pn),
                    "workers": len(prov_workers.get(pn, []))})
    handler._json({"ok": True, "providers": out,
                   "data_month": dm, "data_year": dy,
                   "settings": cfg.get("settings", {}),
                   "company": cfg.get("company", {}),
                   "clients": cfg.get("providers", {})})


def api_save_no(handler, path, body):
    """Print/issue acknowledge — number already assigned at preview time."""
    cfg = load_cfg()
    cur = int(cfg.get("settings", {}).get("invoice_start_no", 1))
    handler._json({"ok": True, "next": "%02d" % cur})


def api_save_cfg(handler, path, body):
    """ক্লায়েন্ট/কন্টাক্ট সেভ (প্রোভাইডার কনফিগ এডিট)।"""
    cfg = load_cfg()
    provs = body.get("providers")
    if isinstance(provs, dict):
        cfg["providers"] = provs
    comp = body.get("company")
    if isinstance(comp, dict):
        cfg["company"] = comp
    sett = body.get("settings")
    if isinstance(sett, dict):
        cfg["settings"] = sett
    save_cfg(cfg)
    handler._json({"ok": True})


GET_ROUTES = {
    "/api/ws/invoice-gen": api_build,
    "/api/ws/invoice-gen-providers": api_providers,
}
POST_ROUTES = {
    "/api/ws/invoice-gen-save": api_save_no,
    "/api/ws/invoice-gen-config": api_save_cfg,
    "/api/ws/invoice-gen-save-pdf": api_save_statements,
    "/api/ws/invoice-gen-save-one": api_save_one,
}
