# ARCHITECTURE.md — AI Time Keeper · গঠন ও প্রবাহ

> স্থানীয় উইন্ডোজ অ্যাপ। কোনো সার্ভার-ডিপ্লয় নেই।
> ড্যাশবোর্ড: `http://127.0.0.1:8765`

---

## ১. ফোল্ডার (ব্যবহারকারী বানিয়েছেন — স্থানান্তর করবেন না)

| ফোল্ডার | কাজ | লেখা যায়? |
|---|---|---|
| `input output\` | **ঠিক ২টি ফাইল** — মাসিক ডাটা শিট + `Total Master sheet.xlsx` | ডাটা শিট: হ্যাঁ (সুরক্ষিত) · **মাস্টার: কখন নয়** |
| `output\` | বটের বানানো Total T শিট | হ্যাঁ (নিরাপদ, নতুন করে বানানো যায়) |
| `backup\` | টাইমস্ট্যাম্প-সহ কপি, ব্যাকআপ কীচেয়ে করা | **মুছবেন না** |
| `months\` | বন্ধ হওয়া মাসের আর্কাইভ (`months\SEP-2026\`) | **মুছবেন না** |
| `logs\`, `ocr_uploads\`, `drive_trash\`, `custom\`, `labor_parts\` | সহায়ক | স্বয়ংক্রিয় |

## ২. কোড-ফাইল

| ফাইল | দায়িত্ব |
|---|---|
| `app.py` | stdlib `http.server`, পোর্ট ৮৭৬৫, ~৭৫টা API, `resolve_file`, ব্যাকআপ/রোলব্যাক |
| `generator.py` | ডাটা শিট পড়া, টোটাল শিট বানানো, `PROVIDER_MAP` |
| `months.py` | `month_clear()` — মাস বন্ধ ও নতুন মাস খোলা |
| `botmem.py`, `cycle.py` | বট-মেমরি ও সাইকেল সহায়ক |
| `dashboard.html` | প্রধান পাতা — Generate · Data Entry · Backup · Settings · Drive · Workspace |
| `workspace.html` + `workspace.js` | কোম্পানি ওয়ার্কস্পেস — প্রফিট, অগ্রিম, ফোন, লেবার |
| `profit.js`, `dash.js`, `unified_add.js` | পাতার জাভাস্ক্রিপ্ট |

### ডেটা-ফাইল (JSON)
`bot_memory.json` (UI + ডিফল্ট মাস/ফাইল) · `provider_config.json` (`PROVIDER_MAP` ওভাররাইড) · `profit_srates/duty/exp/pay/rates.json` · `cycle.json` · `labor_assign.json` · `labor_phones.json`

## ৩. মূল প্রবাহ

```
📁 Upload  →  ডাটা শিট  input output\-এ
📝 Data Entry  →  গ্রিডে সম্পাদনা
🔄 Data Update  →  /api/data-save
                     ├─ backup_file()        লেখার আগে কপি
                     ├─ save_data_sheet()    লেখা
                     ├─ verify_written()     ডিস্ক থেকে যাচাই
                     ├─ roll_back()          ব্যর্থ হলে আগের অবস্থা
                     └─ /api/generate        স্বয়ংক্রিয় টোটাল শিট
✨ Generate  →  সরাসরি টোটাল শিট বানাও
⬇️ Download  →  output\ থেকে নামানো
```

## ৪. টেমপ্লেট-উত্তরাধিকার

`Total Master sheet.xlsx` = **ফরম্যাটের একমাত্র সত্য**। বট কখন ফরম্যাট উদ্ভাবন করে না — মাস্টার থেকে কপি করে।

**প্রোভাইডার → শিট** (`generator.py:165` `PROVIDER_MAP`, `provider_config.json` দিয়ে বদলানো যায়):

| প্রোভাইডার | দৈনিক শিট | গ্র্যান্ড সেকশন |
|---|---|---|
| `mr.nur` | `Nur vai` | `Refarenc of ( Mr. Nur )` |
| `mr.jalil` | **নেই** — শুধু গ্র্যান্ড | `Refarenc of ( Jalil )` |
| `mr.abzol` | `Abzol vai` | `Refarenc of (Abzol )` |
| `mr.somuj` / `somuj` / `mr.samuj` / `samuj` / `mr.samul` / `mr.samil` / `mr.shomuj` | `Somuj ` | `Refarenc of somuj vai )` |
| `mr.shihab` | `Mr.Shihab` | `Refarenc of ( Mr. Shihab )` |
| `mr.shibab` | `Mr.Shibab` | `Refarenc of ( Mr. Shihab )` |
| `mr.amin` | `Mr.Amin` | `Refarenc of ( Mr. Amin )` |
| চিহ্নিত নয় | **নতুন শিট** মাস্টার থেকে ক্লোন | নতুন সেকশন |

## ৫. মাস-রোল (`/api/month-clear` → `months.py:month_clear`)

1. চলতি মাস আর্কাইভ → `months\SEP-2026\`
   - ডাটা শিট + **নতুন করে জেনারেট করা** টোটাল শিট + ৬টি JSON স্ন্যাপশট + `README.txt`
2. নতুন মাসের শিট → `input output\Data sheet oct-26.xlsx`
   - দিনের ঘর খালি, **লোক/রেট/অগ্রিম/গ্যাস বহাল**
   - `A1` = নতুন মাসের ১ তারিখ (`detect_data_month()` সেখান থেকে হিন্ট নেয়)
   - আগের ফাইল থাকলে `-2`, `-3` নাম দেয় — কখন ঢাকে না
3. বট-মেমরি হালনাগাদ

## ৬. এক্সেল-কাঠামো

**ডাটা শিট** — `A1` তারিখ, সারি ২ = হেডার, কলাম: `Sn | Provider | Worker Name | দিন ১–৩১ | … | Rate | … | Advance | Gas`
> ⚠️ **`Provider` কলাম মার্জ করা** (`B3:B9` ইত্যাদি)। Excel-এ সারি ডিলিট করলে মার্জ ভেঙে **লোক চুপিচুপি অন্য প্রোভাইডারে চলে যায়**। নিরাপদ পথ: ঘর **খালি** করুন, বা অ্যাপের `✂️ কাটুন` / `➕ Labour Add` ব্যবহার করুন।

**টাইম শিট (লম্বা নয়, আড়াআড়ি)** — সারি ২ = লোকের নাম কলাম হিসেবে, সারি ৪–৩৪ = দিন ১–৩১, সারি ৩৫ = প্রতি লোকের TOTAL, সারি ৩৭ = **হলুদ `TOTAL HOURS` বার `A37`-এ**।

**চিহ্ন:** অনুপস্থিত `A` = লাল ব্যাকগ্রাউন্ড · রবিবার = লাল অক্ষর · বার = হলুদ ব্যাকগ্রাউন্ড + `medium` কালো বর্ডার।
