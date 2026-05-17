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

echo [1/3] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [2/3] 初始化数据库...
.venv\Scripts\python.exe -c "from backend.database import init_db; init_db(); print('数据库就绪')"

echo [3/3] 启动 Flask 服务器...
echo.
echo 仪表盘地址: http://127.0.0.1:8888
echo 按 Ctrl+C 停止服务器
echo.

start http://127.0.0.1:8888
.venv\Scripts\python.exe -m backend.app

pause
