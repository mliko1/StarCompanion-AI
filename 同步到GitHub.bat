@echo off
chcp 65001 >nul
title 同步到 GitHub
cd /d "%~dp0"
echo ============================================
echo   同步项目到 GitHub
echo ============================================
set /p msg=请输入本次更新说明（直接回车用默认说明）: 
if "%msg%"=="" set msg=更新代码
echo.
echo 正在提交变更...
git add -A
git commit -m "%msg%"
echo 正在推送到 GitHub...
git push
echo.
echo ============================================
echo   完成！按任意键关闭本窗口
echo ============================================
pause >nul
