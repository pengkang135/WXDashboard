@echo off
cd /d "%~dp0"
set "pid="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888" ^| findstr "LISTENING"') do set "pid=%%a"
if "%pid%"=="" (echo WXDashboard is not running - port 8888 free&pause&exit /b)
echo Stopping WXDashboard PID:%pid%
taskkill /PID %pid% /T /F
if errorlevel 1 (echo Stop failed - try Run as Administrator) else (echo WXDashboard stopped)
pause
