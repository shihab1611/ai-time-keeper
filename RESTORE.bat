@echo off
title AI Time Keeper - RESTORE
color 0B
cd /d "%~dp0"
echo.
echo  ============================================
echo   AI Time Keeper - RESTORE
echo  ============================================
echo.
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo    Python NOT found!
    echo    Install: drivers\python-3.12.7-amd64.exe
    echo    CHECK: "Add Python to PATH"
    pause
    exit /b 1
)
echo    OK
echo.
echo [2/5] Installing packages...
pip install openpyxl >nul 2>&1
pip install pywebview >nul 2>&1
echo    OK
echo.
echo [3/5] Creating desktop shortcut...
set DESKTOP=%USERPROFILE%\Desktop
if exist "%USERPROFILE%\OneDrive\Desktop" set DESKTOP=%USERPROFILE%\OneDrive\Desktop
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\AI Time Keeper.lnk'); $s.TargetPath='D:\ai manager\AI Time Keeper App.bat'; $s.WorkingDirectory='D:\ai manager'; $s.IconLocation='D:\ai manager\drivers\ai_time_keeper_v3.ico,0'; $s.WindowStyle=7; $s.Save()"
echo    OK
echo.
echo [4/5] Starting server...
start /min "" python app.py
timeout /t 3 /nobreak >nul
echo    OK
echo.
echo [5/5] Opening dashboard...
start "" http://127.0.0.1:8765
echo    OK
echo.
echo  ============================================
echo   RESTORE COMPLETE!
echo  ============================================
echo.
echo   Dashboard: http://127.0.0.1:8765
echo   Desktop:   AI Time Keeper shortcut
echo.
pause
