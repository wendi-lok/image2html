@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================
echo   Image2Html - 速创API图片生成器
echo ====================================
echo.
echo 正在检查 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.7+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python 环境正常
echo.
echo 正在安装依赖...
pip install -r requirements.txt -q
echo.
echo 正在启动服务...
echo.
start "" python app.py
echo 浏览器将自动打开，如未打开请访问 http://localhost:5000
echo.
timeout /t 1 /nobreak >nul
pause
