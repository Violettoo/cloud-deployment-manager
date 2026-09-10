@echo off
:: Admin Privilege Escalation Check
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [SYSTEM] Admin rights confirmed.
) else (
    echo [SYSTEM] Requesting Administrative privileges...
    :: Relaunch script with admin rights
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit
)

:: Dynamically resolve and navigate to the directory hosting this batch file
cd /d "%~dp0"

:: Launch the Admin UI relative to the current directory
start "" pythonw admin_dashboard.py
exit