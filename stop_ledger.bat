@echo off
cd /d "%~dp0"

:: 1. Stop Flask (port 8888)
set "pid="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888" ^| findstr "LISTENING"') do set "pid=%%a"
if "%pid%"=="" (
    echo [Flask] Not running (port 8888 free)
) else (
    echo [Flask] Stopping PID:%pid%
    taskkill /PID %pid% /T /F >nul 2>&1
    if errorlevel 1 (echo [Flask] Stop failed - try Run as Administrator) else (echo [Flask] Stopped)
)

:: 2. Stop wx daemon (Named Pipe, not TCP - netstat can't see it)
set "wx_found=0"
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq wx.exe" /FO TABLE 2^>nul ^| findstr /R "^wx.exe"') do (
    set "wx_found=1"
    echo [wx-daemon] Stopping PID:%%a
    taskkill /PID %%a /F >nul 2>&1
    if errorlevel 1 (echo [wx-daemon] Stop failed - may need Administrator) else (echo [wx-daemon] Stopped)
)
if %wx_found%==0 echo [wx-daemon] Not running

pause
