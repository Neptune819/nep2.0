@echo off
chcp 65001 >nul
title 停止 NEP 番剧推荐系统

echo.
echo  正在停止服务（端口 5000）...
set FOUND=0
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo  关闭 PID %%P ...
    taskkill /f /pid %%P >nul 2>&1
    set FOUND=1
)

REM 同时关闭后台 cmd 窗口
taskkill /f /fi "WINDOWTITLE eq NEP-Server*" >nul 2>&1

if "%FOUND%"=="1" (
    echo.
    echo  [OK] 服务已停止
) else (
    echo.
    echo  [i] 没有运行中的服务
)
echo.
timeout /t 3 >nul
