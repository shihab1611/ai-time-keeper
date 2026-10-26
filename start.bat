@echo off
REM AI Time Keeper launcher - double-click to start + open dashboard
cd /d "D:\ai manager"
start "AI Time Keeper" "D:\ai Trade\Roxy Ai Trade\.venv\Scripts\python.exe" "D:\ai manager\app.py" --open
