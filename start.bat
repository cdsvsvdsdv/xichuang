@echo off
chcp 65001 >nul
title 西窗
cd /d "%~dp0backend"

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo 西窗已经在运行。
  start "" "http://127.0.0.1:8000"
  echo 已尝试打开浏览器；若没弹出，请手动访问 http://127.0.0.1:8000
  echo.
  pause
  exit /b
)

echo ========================================
echo   西窗 - 个人使用版
echo ========================================
echo.
echo 本机访问：http://127.0.0.1:8000
echo 手机访问：同一 WiFi 下，用下面的 IPv4 地址
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } | Select-Object -ExpandProperty IPAddress"
echo 例：http://192.168.1.10:8000
echo.
echo 首次启动如果弹出防火墙提示，请勾选「专用网络」并允许。
echo 关闭本窗口即可停止服务。
echo.

start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"

.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
