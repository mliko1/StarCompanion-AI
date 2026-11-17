@echo off
chcp 65001 >nul
title 星伴AI 训练系统
cd /d "%~dp0"
echo ============================================
echo   星伴AI 训练系统 正在启动...
echo   请耐心等待约 10 秒，不要关闭本窗口
echo   看到 "Uvicorn running" 即为启动成功
echo   成功后浏览器打开  http://127.0.0.1:8000
echo   手机/平板(同一WiFi)打开  电脑IP:8000
echo   关闭本窗口即停止系统
echo ============================================
.\.venv\Scripts\python.exe -m server.run
pause
