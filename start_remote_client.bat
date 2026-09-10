@echo off
:: Green Hell Secure Bootstrapper
:: Requests Administrator privileges for VFS Symlink execution

net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Lock directory and execute GUI
cd /d "%~dp0"
start "" "client_launcher.exe"
exit