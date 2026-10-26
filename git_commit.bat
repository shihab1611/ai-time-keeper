@echo off
REM ============================================================
REM  git_commit.bat — কোডের ইতিহাস রাখুন (১ ক্লিকে)
REM  ব্যবহার:  git_commit.bat  "এখানে পরিবর্তনের কারণ"
REM  (মেসেজ না দিলে "update" লেখা হবে)
REM ============================================================
cd /d "%~dp0"
set MSG=%~1
if "%MSG%"=="" set MSG=update
git add -A
git commit -m "%MSG%"
echo.
echo --- শেষ ৫টি কমিট ---
git --no-pager log --oneline -5
pause
