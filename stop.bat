@echo off
chcp 65001 >nul
title 停止西窗

set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
  set FOUND=1
)

if "%FOUND%"=="1" (
  echo 西窗已停止。
) else (
  echo 没有发现正在运行的西窗服务。
)
echo.
pause
