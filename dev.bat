@echo off
chcp 65001 >nul
title 西窗开发模式
cd /d "%~dp0"

echo 启动开发模式：后端 8000 + 前端 5173
start "西窗后端" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
start "西窗前端" cmd /k "cd /d %~dp0frontend && npm run dev -- --host"

timeout /t 3 >nul
start http://localhost:5173
