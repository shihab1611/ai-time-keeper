@echo off
title AI Time Keeper
cd /d "%~dp0"
"D:\ai Trade\Roxy Ai Trade\.venv\Scripts\python.exe" "app_window.py"
if errorlevel 1 pause
