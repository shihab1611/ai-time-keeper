# AI Time Keeper — Windows নতুন করে দিলে রিকভারি (D:\ai manager নিরাপদ, Windows C:-তে)

## 0. আগে (এখনই, ২ মিনিট)
- [ ] D:\ai manager পুরো OneDrive/পেনড্রাইভে কপি (backup\ সহ)
- [ ] OneDrive অ্যাকাউন্ট মনে রাখুন (somuj vai ফোল্ডার সিঙ্ক হয়)

## 1. Windows + ড্রাইভার + OneDrive
- Windows ইনস্টল → OneDrive লগইন → somuj vai ফোল্ডার সিঙ্ক হতে দিন
- ফোল্ডার পাথ একই রাখুন: C:\Users\Admin\OneDrive\Desktop\somuj vai
  (ইউজারনাম বদলালে app.py-তে DRIVE_DIR বদলাতে হবে)

## 2. Python
- `drivers\python-3.12.7-amd64.exe` ডাবল-ক্লিক (Install-এ "Add to PATH" টিক দিন)
  (বট .exe নিজে চালাতে পারে না — এটা হাতে একবার)
- PowerShell-এ যাচাই: python --version

## 3. বট চালু
- D:\ai manager ফোল্ডার ফেরত রাখুন (পেনড্রাইভ/OneDrive থেকে)
- cd "D:\ai manager"
- python -m venv "D:\ai Trade\Roxy Ai Trade\.venv"  (পুরনো venv না থাকলে)
- venv Scripts\python.exe -m pip install -r requirements.txt
- AI_Time_Keeper_Start.bat ডাবল-ক্লিক → http://127.0.0.1:8765

## 4. OCR থাকলে (Phase 1 করা হলে)
- `drivers\tesseract-ocr-w64-setup-*.exe` ডাবল-ক্লিক (হাতে একবার)
- venv-তে pip প্যাকেজ বট চালু হলেই অটো বসবে (নেট থাকলে)

## 5. OneDrive ক্লাউড লগইন (rclone) — Windows দিলে আবার করতে হবে
- কারণ: লগইন টোকেন C:-তে (`%APPDATA%\rclone\rclone.conf`) থাকে, Windows-এর সাথে মুছে যায়
- বট + `drivers\rclone.exe` D:-তে বেঁচে থাকে — আবার ডাউনলোড লাগে না, Azure/Client ID-ও লাগে না
- পদ্ধতি: `drivers\README.md`-এর "OneDrive ক্লাউড (rclone)" অংশ (rclone config → onedrive → Microsoft লগইন, ২ মিনিট)

## মনে রাখুন
- atk_* সেটিংস ব্রাউজারে থাকে (localStorage) — নতুন ব্রাউজার/PC-তে আবার বাছতে হবে
- backup\ ফোল্ডার = নিরাপত্তা — মুছবেন না
- PIN ভুলে গেলে: সার্ভার বন্ধ করে D:\ai manager\.pinlock ফাইল মুছে চালু করুন
- User ID ভুলে গেলে: সার্ভার বন্ধ করে D:\ai manager\.users ফাইল মুছে চালু করুন (সব ইউজার যাবে, আবার বানান)
