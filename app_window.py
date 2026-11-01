# -*- coding: utf-8 -*-
"""
AI Time Keeper — Desktop App Window (PyWebView)
এই ফাইলটি শুধু ড্যাশবোর্ডকে একটা আলাদা ডেস্কটপ উইন্ডোতে দেখায়।
app.py কিংবা dashboard.html কোনোটাই বদলায় না।
ব্রাউজারে খোলাও যেভাবে চালু ছিল, সেভাবেই থাকবে।

ব্যবহার:
    python app_window.py            (সার্ভার চালু থাকলে সরাসরি উইন্ডো খুলবে)
    python app_window.py --new      (নতুন সার্ভার চালিয়ে উইন্ডো খুলবে)

শর্টকাট বানাতে:  ডাবল-ক্লিক করলেই চলবে।
"""
import os
import sys
import time
import socket
import urllib.request
import subprocess
import webview

BASE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8765"
PY = sys.executable          # যে python দিয়ে এটা চলছে


def server_alive(port=8765):
    """পোর্টে সার্ভার চলছে কিনা দেখে।"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_server(timeout=20):
    """সার্ভার রেডি হওয়া পর্যন্ত অপেক্ষা করে।"""
    end = time.time() + timeout
    while time.time() < end:
        if server_alive():
            try:
                urllib.request.urlopen(URL, timeout=2).read()
                return True
            except Exception:
                pass
        time.sleep(0.5)
    return False


def start_server():
    """আলাদা প্রসেসে app.py চালু করে।"""
    env = dict(os.environ, PORT="8765")   # উইন্ডো ৮৭৬৫-এই অপেক্ষা করে — সার্ভারও সেখানেই চালু হোক
    subprocess.Popen(
        [PY, os.path.join(BASE, "app.py")],
        cwd=BASE,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,   # কালো কনসোল উইন্ডো লাগবে না
    )


def main():
    force_new = "--new" in sys.argv

    if force_new or not server_alive():
        start_server()
        if not wait_for_server():
            print("সার্ভার চালু হয়নি — ব্রাউজারে হাতে চেষ্টা করুন:", URL)
            sys.exit(1)

    # উইন্ডো টাইটেল + সাইজ
    webview.create_window(
        "AI Time Keeper",
        URL,
        width=1360,
        height=860,
        min_size=(980, 620),
        resizable=True,
        background_color="#0f172a",     # খোলার সময় নেভি ব্যাকগ্রাউন্ড
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
