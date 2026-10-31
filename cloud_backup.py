# -*- coding: utf-8 -*-
"""AI Time Keeper — ক্লাউড ব্যাকআপ ডাউনলোডার

প্রতিদিন ক্লাউড অ্যাপ থেকে পুরো ডেটার ZIP (শিট, ইনভয়েস+PDF, মাস-আর্কাইভ,
অগ্রিম-খাতা, কনফিগ) নামিয়ে OneDrive ফোল্ডারে রাখে — OneDrive ডেস্কটপ
সেটা আপনাআপনি মাইক্রোসফট ক্লাউডে সিঙ্ক করে।

Windows Task Scheduler দিনে একবার চালায়। কনফিগ: cloud_backup_config.json
শুধু পাইথনের নিজের লাইব্রেরি লাগে — কিছু ইনস্টল করতে হয় না।
"""
import http.cookiejar
import json
import os
import urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(BASE, "cloud_backup_config.json")
KEEP = 60          # OneDrive-এ সর্বশেষ কতগুলো ব্যাকআপ রাখা হবে
PREFIX = "AI_Time_Keeper_CLOUD_BACKUP_"


def load_cfg():
    with open(CFG_FILE, encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_cfg()
    url = str(cfg["url"]).rstrip("/")
    dest = cfg["dest"]
    email = str(cfg["email"])
    password = str(cfg["password"])
    os.makedirs(dest, exist_ok=True)

    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    req = urllib.request.Request(
        url + "/api/auth/login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req, timeout=180) as r:
        body = json.loads(r.read().decode("utf-8"))
    if not body.get("ok"):
        raise SystemExit("লগইন ফেল: %s" % body.get("error"))

    with op.open(url + "/api/backup", timeout=900) as r:
        data = r.read()
    if not data.startswith(b"PK"):
        raise SystemExit("ZIP পাওয়া যায়নি — উত্তরের শুরু: %r" % data[:80])

    out = os.path.join(dest, PREFIX + datetime.now().strftime("%Y%m%d_%H%M") + ".zip")
    with open(out, "wb") as f:
        f.write(data)
    print("OK:", out, "(%d KB)" % (len(data) // 1024))

    olds = sorted(f for f in os.listdir(dest)
                  if f.startswith(PREFIX) and f.endswith(".zip"))
    for f in olds[:-KEEP]:
        try:
            os.remove(os.path.join(dest, f))
            print("পুরনো ব্যাকআপ মুছে গেল:", f)
        except OSError:
            pass


if __name__ == "__main__":
    main()
