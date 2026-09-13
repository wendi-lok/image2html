@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Image2Html - 速创 API 图片生成器

echo ==========================================
echo    Image2Html - 速创API图片生成器
echo ==========================================
echo.

rem ---------------------------------------------------------------
rem 1) 找一个真正能用的 Python
rem    不能只用 where python：Windows 的“应用执行别名”会让 where 找到一个
rem    商店占位符，执行后只会弹出微软商店，这曾是“一键启动用不了”的原因之一。
rem    这里会实际执行一次 import sys 来验证解释器是真能跑的。
rem ---------------------------------------------------------------
set "PYEXE="

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYEXE=py -3"
    )
)

if not defined PYEXE (
    echo [错误] 没有找到可用的 Python 3
    echo.
    echo   请到 https://www.python.org/downloads/ 下载安装 Python 3.8 及以上，
    echo   安装时务必勾选 "Add python.exe to PATH"，装完重开本文件即可。
    echo.
    pause
    exit /b 1
)
echo [1/2] Python 环境正常（%PYEXE%）
echo.

rem ---------------------------------------------------------------
rem 2) 本项目零第三方依赖，不需要 pip install，
rem    既加快启动，也避免无网络时卡在这一步。
rem ---------------------------------------------------------------
echo [2/2] 正在启动服务，浏览器会自动打开页面...
echo.
echo   ------------------------------------------
echo    页面地址：http://127.0.0.1:5000
echo    停止服务：关闭本窗口，或按 Ctrl+C
echo   ------------------------------------------
echo.

%PYEXE% app.py
set "RC=%errorlevel%"

echo.
if not "%RC%"=="0" (
    echo [错误] 程序异常退出，错误码 %RC%
    echo 请把上面的报错信息截图反馈。
) else (
    echo 服务已停止。
)
echo.
pause
endlocal
