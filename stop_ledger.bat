@echo off
title 停止 WXDashboard
cd /d "%~dp0"

set "found="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888.*LISTENING"') do (
    set "pid=%%a"
    set "found=1"
)

if not defined found (
    echo WXDashboard 未在运行 (端口 8888 无监听进程)
    pause
    exit
)

echo 找到 PID: %pid%，正在终止...
taskkill /PID %pid% /T /F
if errorlevel 1 (
    echo 终止失败，请手动结束: taskkill /PID %pid% /F
) else (
    echo WXDashboard 已停止。
)
pause
