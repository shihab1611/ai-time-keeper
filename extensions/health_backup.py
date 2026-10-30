# -*- coding: utf-8 -*-
"""
health_backup.py — অটো ব্যাকআপ + হেলথ চেক এক্সটেনশন
(অনুমোদিত ইম্প্রুভমেন্ট ১ ও ২ — ইঞ্জিন/app.py কোনোটাই ছোঁয় না)

GET  /api/health         → সিস্টেমের অবস্থা (বাংলায় সমস্যার তালিকা)
POST /api/ws/backup-now  → এখনই ZIP ব্যাকআপ (D: + OneDrive)

অটো ব্যাকআপ: সার্ভার চালু হওয়ার পর (আজ ব্যাকআপ না থাকলে) + প্রতিদিন রাত ৯টায়
ZIP-এ যা যায়: input output, extensions, months, logs + রুটের কোড/কনফিগ ফাইল
ZIP-এ যায় না: drivers, output, backup, __pycache__, বড় আর্কাইভ ফাইল
"""
import os
import sys
import json
import time
import zipfile
import shutil
import threading
import subprocess

_here = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(_here)                      # D:\ai manager
STATE_FP = os.path.join(_here, "backup_state.json")
AUTO_DIR = os.path.join(BASE, "backup", "AUTO")
ONEDRIVE_DIR = os.path.join(os.path.expanduser("~"), "OneDrive", "ai manager", "backup")
KEEP = 14                    # প্রতিটি জায়গাযে ১৪টা অটো ZIP রাখবে, বাকি পুরনো মুছবে
BACKUP_HOUR = 21              # প্রতিদিন রাত ৯টা (সার্ভার চালু থাকলে)
MAX_FILE = 40 * 1024 * 1024   # একটা ফাইলের সর্বোচ্চ ৪০ MB

INCLUDE_DIRS = ["input output", "extensions", "months", "logs", "LOCKED"]
INCLUDE_ROOT_EXT = (".html", ".js", ".py", ".json", ".md", ".txt",
                    ".bat", ".users", ".conf", ".ps1")
SKIP_NAMES = {"__pycache__", ".git"}

# এই রুটগুলো না থাকলে মানে ওই এক্সটেনশন লোডই হয়নি
CRITICAL_GET = [
    "/api/health",
    "/api/ws/invoice-gen",
    "/api/ws/invoice-gen-providers",
    "/api/ws/company-invoice",
    "/api/ws/company-invoice-providers",
    "/api/ws/invoice",
]
CRITICAL_POST = [
    "/api/ws/backup-now",
    "/api/ws/invoice-gen-save-one",
    "/api/ws/company-invoice-save-one",
    "/api/ws/invoice-add",
]

STATE = {"last_ok": None, "last_local": None, "last_onedrive": None,
         "last_err": None, "files": 0, "size": 0, "runs": 0}
_lock = threading.Lock()
_started = False


# ---------------------------------------------------------------- state
def _load_state():
    try:
        with open(STATE_FP, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            STATE.update(data)
    except Exception:
        pass


def _save_state():
    try:
        with open(STATE_FP, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- backup
def _prune(folder):
    """পুরনো অটো ZIP রাখবে শুধু KEEP-এর মধ্যে।"""
    try:
        zips = sorted((os.path.join(folder, f) for f in os.listdir(folder)
                       if f.startswith("AI_Time_Keeper_AUTO_") and f.endswith(".zip")),
                      key=os.path.getmtime, reverse=True)
        for old in zips[KEEP:]:
            try:
                os.remove(old)
            except OSError:
                pass
    except OSError:
        pass


def make_zip(dest_dir):
    """নির্ধারিত ফোল্ডারগুলোর ZIP বানিয়ে dest_dir-এ রাখে। (path, file_count, size)"""
    os.makedirs(dest_dir, exist_ok=True)
    name = "AI_Time_Keeper_AUTO_%s.zip" % time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(dest_dir, name)
    n = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d in INCLUDE_DIRS:
            root = os.path.join(BASE, d)
            if not os.path.isdir(root):
                continue
            for dp, dns, fns in os.walk(root):
                dns[:] = [x for x in dns if x not in SKIP_NAMES]
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    try:
                        if os.path.getsize(fp) > MAX_FILE:
                            continue
                        z.write(fp, os.path.relpath(fp, BASE))
                        n += 1
                    except OSError:
                        pass
        for fn in sorted(os.listdir(BASE)):
            fp = os.path.join(BASE, fn)
            if os.path.isfile(fp) and fn.lower().endswith(INCLUDE_ROOT_EXT):
                try:
                    if os.path.getsize(fp) > MAX_FILE:
                        continue
                    z.write(fp, fn)
                    n += 1
                except OSError:
                    pass
    return path, n, os.path.getsize(path)


def do_backup():
    """লোকাল ZIP + OneDrive কপি। ফলাফল ডিকশনারি ফেরায়।"""
    if not _lock.acquire(False):
        return {"ok": False, "err": "ব্যাকআপ আগে থেকেই চলছে", "busy": True}
    try:
        t0 = time.time()
        local_ok, od_ok, err = False, False, ""
        local_path = ""
        try:
            local_path, n, size = make_zip(AUTO_DIR)
            local_ok = True
            _prune(AUTO_DIR)
        except Exception as e:
            err = "লোকাল ব্যাকআপ: %s" % e
        # OneDrive কপি (থাকলে)
        od_err = ""
        if local_ok:
            try:
                if os.path.isdir(os.path.dirname(ONEDRIVE_DIR)) or os.path.isdir(ONEDRIVE_DIR):
                    os.makedirs(ONEDRIVE_DIR, exist_ok=True)
                    dst = os.path.join(ONEDRIVE_DIR, os.path.basename(local_path))
                    shutil.copy2(local_path, dst)
                    od_ok = True
                    _prune(ONEDRIVE_DIR)
                else:
                    od_err = "OneDrive ফোল্ডার পাওয়া যায়নি"
            except Exception as e:
                od_err = str(e)
        STATE["runs"] = int(STATE.get("runs") or 0) + 1
        if local_ok:
            STATE["last_ok"] = time.time()
            STATE["last_local"] = local_path
            STATE["last_onedrive"] = (ONEDRIVE_DIR if od_ok else STATE.get("last_onedrive"))
            STATE["files"] = n
            STATE["size"] = size
            STATE["last_err"] = od_err or None
            STATE["onedrive_err"] = od_err or None
        else:
            STATE["last_err"] = err
        _save_state()
        return {"ok": local_ok, "err": err or None, "path": local_path,
                "files": n if local_ok else 0,
                "size": (size if local_ok else 0),
                "onedrive": od_ok, "onedrive_err": od_err or None,
                "took": round(time.time() - t0, 1)}
    finally:
        _lock.release()


def _done_today():
    last = STATE.get("last_ok") or 0
    return time.strftime("%Y-%m-%d", time.localtime(last)) == time.strftime("%Y-%m-%d")


def _auto_loop():
    """সার্ভার চালুর ২৫ সেকেন্ড পর + প্রতিদিন রাত ৯টায় অটো ব্যাকআপ।"""
    time.sleep(25)
    try:
        if not _done_today():
            do_backup()
    except Exception:
        pass
    while True:
        try:
            now = time.localtime()
            nxt = time.mktime((now.tm_year, now.tm_mon, now.tm_mday,
                               BACKUP_HOUR, 0, 0, 0, 0, -1))
            if nxt <= time.time():
                nxt += 24 * 3600
            time.sleep(max(5.0, nxt - time.time()))
            do_backup()
        except Exception:
            time.sleep(60)


# ---------------------------------------------------------------- health
def _check_lock():
    vp = os.path.join(BASE, "LOCKED", "verify.py")
    if not os.path.isfile(vp):
        return {"ok": False, "msg": "LOCKED/verify.py নেই"}
    try:
        r = subprocess.run([sys.executable, vp], capture_output=True,
                           timeout=45, cwd=BASE)
        out = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace").strip()
        lines = [l for l in out.splitlines() if l.strip()]
        ok = r.returncode == 0 and lines and lines[0].startswith("OK")
        return {"ok": bool(ok), "msg": lines[-1] if lines else out[:200] or "কোনো ফলাফল নেই"}
    except Exception as e:
        return {"ok": False, "msg": "ভেরিফাই চলেনি: %s" % e}


def _backup_status():
    last = STATE.get("last_ok")
    age_h = round((time.time() - last) / 3600.0, 1) if last else None
    return {
        "last_ok": last,
        "last_ok_str": time.strftime("%d %b %Y %H:%M", time.localtime(last)) if last else None,
        "age_hours": age_h,
        "path": STATE.get("last_local"),
        "files": STATE.get("files"), "size": STATE.get("size"),
        "onedrive": bool(STATE.get("last_onedrive")),
        "onedrive_err": STATE.get("onedrive_err"),
        "err": STATE.get("last_err"),
        "runs": STATE.get("runs"),
    }


def api_health(handler, path, q):
    problems, warns = [], []
    # ১) এক্সটেনশন রুট লোড হয়েছে কিনা
    m = sys.modules.get("__main__")
    g = getattr(m, "_EXT_GET", None) or {}
    p = getattr(m, "_EXT_POST", None) or {}
    missing = [r for r in CRITICAL_GET if r not in g]
    missing += [r for r in CRITICAL_POST if r not in p]
    if missing:
        problems.append("এক্সটেনশন লোড হয়নি — এই কাজগুলো বন্ধ: " + ", ".join(missing))
    # ২) ইঞ্জিন লক
    lock = _check_lock()
    if not lock["ok"]:
        problems.append("⚠️ ইঞ্জিন লক ভেঙে গেছে — " + str(lock["msg"]))
    # ৩) ব্যাকআপ
    bak = _backup_status()
    if not bak["last_ok"]:
        warns.append("এখনো কোনো অটো ব্যাকআপ হয়নি (প্রথমটা সার্ভার চালু হওয়ার ২৫ সেকেন্ড পর হবে)")
    elif bak["age_hours"] is not None and bak["age_hours"] > 30:
        warns.append("সর্বশেষ ব্যাকআপ %s ঘণ্টা আগে — আজকের ব্যাকআপ হয়নি" % bak["age_hours"])
    if bak.get("onedrive_err"):
        warns.append("OneDrive কপি ব্যর্থ: %s" % bak["onedrive_err"])
    status = "error" if problems else ("warn" if warns else "ok")
    handler._json({
        "ok": True, "status": status,
        "problems": problems, "warns": warns,
        "lock": lock, "backup": bak,
        "routes": {"get": len(g), "post": len(p)},
        "server": "running", "port": 8765,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


def api_backup_now(handler, path, body):
    handler._json(do_backup())


# ---------------------------------------------------------------- boot
_load_state()
GET_ROUTES = {"/api/health": api_health}
POST_ROUTES = {"/api/ws/backup-now": api_backup_now}

if not _started:
    _started = True
    threading.Thread(target=_auto_loop, daemon=True).start()
    print("[ext] health_backup.py: অটো ব্যাকআপ থ্রেড চালু (প্রতিদিন %02d:00)" % BACKUP_HOUR)
