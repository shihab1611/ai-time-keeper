# AGENTS.md — AI Time Keeper · কাজের কঠিন নিয়ম

> এই ফাইলটা **সত্যের উৎস**। কোড বদলানোর আগে এটা পড়ুন।
> প্রতিটি নিয়মের পাশে কারণ দেওয়া আছে — কারণ না বুঝে নিয়ম ভাঙবেন না।

---

## 🚫 MUST NOT — এগুলো কখনই করবেন না

```text
1.  NEVER write to "input output\Total Master sheet.xlsx".  COPY ONLY.
2.  NEVER write an .xlsx without backup_file() + verify_written(), and
    roll_back() on any failure.
3.  NEVER turn autoBackup off. There is no toggle — do not add one.
4.  NEVER delete or overwrite anything in backup\ or months\.
5.  NEVER hand-write Bengali as \uXXXX escapes.  Use real UTF-8 text.
6.  NEVER restructure the folders.  The layout below is user-built.
7.  NEVER change Profit / Site Rate inside any Excel file — JSON only.
8.  NEVER delete or restore a user's file without explicit approval.
9.  NEVER add a database, login, hosting, or a framework rewrite.
10. NEVER assume a file is stale — ask before removing it.
```

---

## ১. ফাইল-সুরক্ষা (সবচেয়ে গুরুত্বপূর্ণ)

| ধাপ | কোথায় | কী করে |
|---|---|---|
| `backup_file(path)` | `app.py:1018` | লেখার **আগে** কপি নেয় — টগল বন্ধ, সবসময় চালু |
| `verify_written(path)` | `app.py:772` | ডিস্ক থেকে **আবার পড়ে** লেখা হয়েছে কিনা দেখে |
| `roll_back(path, bak, existed)` | `app.py:788` | কিছু একটা হারালে **আগের অবস্থায় ফেরায়** |

- ইউজার Excel খোলা রাখলে (`~$` লক-ফাইল) বট **লেখে না** → HTTP `423` + বাংলা অ্যালার্ট।
- `resolve_file()` (`app.py:1129`) ফাইল খোঁজে: `input output\` → `D:\ai manager\` → whitespace-normalized ম্যাচ।

> **নিয়ম:** কোনো ফাইলেও লেখার আগে উপরের তিনটে ধাপ সম্পূর্ণ হওয়া বাধ্যতামূলক।

## ২. ভাষা

- ইউআই বাংলা-প্রথম, English টগল আছে (`dashboard.html`)।
- কী-স্ট্রিং: `atk_theme`, `atk_lang` — দুই পাতায় যৌথ।
- বাংলা **সত্যিকারের UTF-8** টেক্সট, কখনই `\u09xx` এস্কেপ নয়।

## ৩. অনুমতি

- কোনো পরিবর্তনের আগে **অনুমতি নিতে হবে**।
- ফাইল মুছা/সরানো/ফেরানো — সবই আলাদা অনুমতি চায়।
- ব্যাকআপ থেকে কিছু ফেরানোও অনুমতি ছাড়া নয়।

## ৪. পরীক্ষা (প্রতিবার পরিবর্তনের পর)

| যাচাই | প্রত্যাশা |
|---|---|
| টেমপ্লেট ড্রপডাউন | `Total Master sheet.xlsx` সিলেক্টেড |
| টোটাল ঘরের ঘর | `A37` (মাস্টারের মতো) |
| স্টাইল-পার্থক্য মাস্টারের সাথে | `০` |
| কাটা লোক | আউটপুটে **ফিরে আসে না** |
| ডাটা শিট লোডে সতর্কতা | পরিষ্কার শিটে **০** — মার্জ-যাচাই (`_check_provider_blocks` + `_check_declared_providers`) চালু |
| ব্রাউজার কনসোল | ০ এরর |

---

## ৫. যা করতে হবে (সংক্ষেপে)

- পরিবর্তনের আগে **পুরনো কোড পড়ুন**। অহেতুক রিরাইট করবেন না।
- ফরম্যাটের সত্য উৎস হলো **`Total Master sheet.xlsx`**, কোড নয়। সন্দেহ হলে মাস্টার খুলে দেখুন।
- পরিবর্তন ছোট রাখুন। কাজ না করলে সাইলেন্টলি ফেরিয়ে দিন।
- অসফল হলে **কারণ** বলুন — আঁচার দিয়ে ঠিক করবেন না।
