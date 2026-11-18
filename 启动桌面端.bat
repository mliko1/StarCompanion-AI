@echo off
chcp 65001 >nul
title 星伴AI 儿童训练端
cd /d "%~dp0"
echo ============================================
echo   星伴AI 儿童训练端 正在启动...
echo   请先确保「启动训练系统.bat」的后端窗口已开启
echo   若提示连不上后端，请检查后端窗口是否还在
echo ============================================
.\.venv\Scripts\python.exe desktop\main_window.py
pause
