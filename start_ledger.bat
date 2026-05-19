@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Laldia 港湾微信群台账
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行: python -m venv .venv
    pause
    exit /b 1
)

echo [1/4] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [2/4] 检查已有进程...
set "PORT=8888"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% .*LISTENING" 2^>nul') do (
    set "PID=%%a"
    goto :found
)
goto :notfound

:found
echo   发现已有 Flask 进程 (PID: %PID%)，正在关闭...
taskkill /PID %PID% /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo   已关闭旧进程
echo.

:notfound

echo [3/4] 初始化数据库...
.venv\Scripts\python.exe -c "from backend.database import init_db; init_db(); print('数据库就绪')"

echo [4/4] 启动 Flask 服务器...
echo.
echo 仪表盘地址: http://127.0.0.1:8888
echo 按 Ctrl+C 停止服务器
echo.

start http://127.0.0.1:8888
.venv\Scripts\python.exe -m backend.app

pause
