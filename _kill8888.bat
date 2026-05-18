@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F /T >nul 2>&1 && echo Killed PID %%a || echo Failed PID %%a
)
