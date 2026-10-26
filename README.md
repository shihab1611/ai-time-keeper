# AI Time Keeper

Data sheet → Total T sheet • হুবহু ফরমেট • আধুনিক ড্যাশবোর্ড

## 📖 পড়ার আগে (Docs)
- [`AGENTS.md`](AGENTS.md) — কঠিন নিয়ম, যা **কখনই** করবেন না
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — ফোল্ডার, মূল প্রবাহ, প্রোভাইডার-ম্যাপ, মাস-রোল
- [`SCOPE.md`](SCOPE.md) — কী আছে, কী **যোগ হবে না**
- [`RECOVERY.md`](RECOVERY.md) — সমস্যা হলে ফেরানোর ধাপ

## Location
`D:\ai manager`

## 📁 Folders
| ফোল্ডার | কাজ |
|---|---|
| `input output\` | **ঠিক ২টি ফাইল** — মাসিক ডাটা শিট + `Total Master sheet.xlsx` |
| `output\` | বটের বানানো Total T শিট (নামানো যায়, নতুন করে বানানো যায়) |
| `backup\` | টাইমস্ট্যাম্প-সহ কপি — **স্বয়ংক্রিয়, টগল বন্ধ** |
| `months\` | বন্ধ হওয়া মাসের আর্কাইভ (`months\SEP-2026\`) |
| `logs\`, `ocr_uploads\`, `drive_trash\` | সহায়ক |

## Files
- `app.py` — dashboard server (`http://127.0.0.1:8765`), ~৭৫টা API, ব্যাকআপ/রোলব্যাক/লক
- `generator.py` — Data → Total T logic, `PROVIDER_MAP`
- `months.py` — মাস বন্ধ ও নতুন মাস খোলা
- `dashboard.html` — প্রধান পাতা (Generate · Data Entry · Backup · Settings · Drive · Workspace)
- `workspace.html` + `workspace.js` — কোম্পানি ওয়ার্কস্পেস (প্রফিট, অগ্রিম, ফোন, লেবার)
- `bot_memory.json` — ভাষা, থিম, ডিফল্ট মাস/ফাইল
- `provider_config.json` — প্রোভাইডার → শিট নাম বদলানো যায়
- `output/` — জেনারেট করা Total T ফাইল

## Run
```powershell
& "D:\ai Trade\Roxy Ai Trade\.venv\Scripts\python.exe" "D:\ai manager\app.py"
```
Open: http://127.0.0.1:8765

Or double-click `AI_Time_Keeper_Start.bat`.

## Use
1. মাসিক Data sheet রাখুন **`input output\`**-এ (Table 1: Sn, Provider, Worker Name, 1..31, Rate, Advance, Gas)
2. Dashboard → **📝 Data Entry** ট্যাবে লোক যোগ/কাটুন, দিন বসান
3. **🔄 Data Update** চাপুন — ডাটা শিটে সেভ + **নিজে থেকেই** টোটাল শিট বানায়
4. বা সরাসরি **✨ Total T বানাও** (Data ফাইল + **Template = `Total Master sheet.xlsx`** + মাস/বছর)
5. **⬇️ Download** — `output\` থেকে

## Rules
- `A` / `S` / `SUNDAY` / খালি = ০ ঘণ্টা
- রবিবার বট **নিজে** বসায় (SUNDAY)
- প্রোভাইডার গ্রুপ অনুযায়ী দৈনিক শিট + গ্র্যান্ড ব্যালান্স (মাস্টার হুবহু ক্লোন)
- **মোট ঘণ্টা** = দিনের ঘরগুলোর যোগ (শিটের নিজের `Total Duty hour` বাদ)
- **Total Balance** = ঘণ্টা × রেট
- **Grand Balance** = Total Balance − অগ্রিম − গ্যাস বিল
- `Mr.Jalil` → শুধু গ্র্যান্ড, দৈনিক শিট নেই
- চিহ্নিত নয় এমন প্রোভাইডার → মাস্টার থেকে **নতুন শিট ক্লোন** হয়

## 🛡️ Safety (কখন ভাঙবেন না)
- **`Total Master sheet.xlsx` কখন লেখা হয় না** — শুধু কপি হয়
- লেখার **আগে** ব্যাকআপ → লেখা → ডিস্ক থেকে **যাচাই** → ব্যর্থ হলে **আগের অবস্থায় ফেরানো**
- Excel খোলা থাকলে বট লেখে **না** (HTTP 423 + বাংলা অ্যালার্ট)
- **প্রফিট / সাইট রেট কখন Excel-এ লেখা হয় না** — শুধু JSON (`profit_*.json`)
- `backup\` ও `months\` থেকে কিছু **মুছবেন না**
- ইউআই বাংলা-প্রথম, English টগল আছে

## ⚠️ একটা সতর্কতা
ডাটা শিটের **Provider কলাম মার্জ করা** (`B3:B9` ইত্যাদি)। সারি ডিলিট করার বদলে **ঘর খালি** করুন, অথবা অ্যাপের `✂️ কাটুন` / `➕ Labour Add` ব্যবহার করুন। বিস্তারিত: [`ARCHITECTURE.md`](ARCHITECTURE.md) §৬
