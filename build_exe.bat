@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 打包 Image2Html 为免 Python 的 EXE

echo ==========================================
echo    打包 Image2Html（Windows 免安装版）
echo ==========================================
echo.
echo 说明：打包后的 exe 自带 Python 运行时，
echo       别人拿到不需要装 Python 就能直接运行。
echo 注意：打包本机需要 Python + PyInstaller。
echo.

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
    echo [错误] 没有找到可用的 Python 3，无法打包。
    echo   下载：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检查 PyInstaller...
%PYEXE% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo       未安装，正在安装...
    %PYEXE% -m pip install -U pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)
for /f "delims=" %%v in ('%PYEXE% -m PyInstaller --version') do echo       PyInstaller %%v

echo.
echo [2/4] 清理旧的构建产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Image2Html.spec del /q Image2Html.spec

echo.
echo [3/4] 开始打包（首次大约 1-3 分钟）...
%PYEXE% -m PyInstaller --onedir --noconfirm --clean ^
    --name Image2Html ^
    --add-data "templates;templates" ^
    --exclude-module tkinter ^
    --exclude-module unittest ^
    --exclude-module pydoc ^
    --exclude-module test ^
    --exclude-module distutils ^
    --exclude-module lib2to3 ^
    app.py
if errorlevel 1 (
    echo [错误] 打包失败，请把上面的报错截图反馈。
    pause
    exit /b 1
)

echo.
echo [4/4] 生成启动入口、说明与分发压缩包...

rem 启动.bat 全部用 ASCII，避免 cmd 的中文编码坑
> "dist\Image2Html\启动.bat" echo @echo off
>> "dist\Image2Html\启动.bat" echo cd /d "%%~dp0"
>> "dist\Image2Html\启动.bat" echo title Image2Html
>> "dist\Image2Html\启动.bat" echo echo Starting Image2Html ...
>> "dist\Image2Html\启动.bat" echo echo Close this window to stop the server.
>> "dist\Image2Html\启动.bat" echo echo.
>> "dist\Image2Html\启动.bat" echo Image2Html.exe
>> "dist\Image2Html\启动.bat" echo if errorlevel 1 (
>> "dist\Image2Html\启动.bat" echo     echo.
>> "dist\Image2Html\启动.bat" echo     echo [ERROR] Failed to start. Please read the message above.
>> "dist\Image2Html\启动.bat" echo     pause
>> "dist\Image2Html\启动.bat" echo )

rem 说明文件用 PowerShell 以 UTF-8 写出，避免乱码
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = @'" ^
  "Image2Html - 速创 API 图片生成器（免安装版）" ^
  "================================================" ^
  "" ^
  "【怎么用】" ^
  "  双击 Image2Html.exe（或 启动.bat），浏览器会自动打开页面。" ^
  "  不需要安装 Python，不需要联网安装任何依赖。" ^
  "" ^
  "【第一次用】" ^
  "  点右上角齿轮图标，填入速创 API 密钥，保存即可。" ^
  "" ^
  "【怎么关】" ^
  "  关闭那个黑色命令行窗口即停止服务；或在窗口里按 Ctrl+C；" ^
  "  如果关不掉，用任务管理器结束 Image2Html.exe。" ^
  "" ^
  "【重要提醒】" ^
  "  1. 不要把 Image2Html.exe 单独拖出来用！它必须和同目录的 _internal 文件夹放在一起。" ^
  "     分发时请把整个 Image2Html 文件夹一起打包。" ^
  "  2. 参考图可以直接拖进窗口，会自动上传图床换公网直链。" ^
  "     默认走 UAPI 图床，免注册可用（匿名每天 10 张，填免费 Key 可不限量）。" ^
  "  3. API 密钥、图床配置、历史记录都保存在同目录的 data 文件夹里，换电脑记得备份。" ^
  "  4. 端口默认 5000；若被占用会自动顺延，终端里会打印实际地址。" ^
  "" ^
  "【常见问题】" ^
  "  Q: 双击后闪一下就没了？" ^
  "  A: 说明启动报错。请用 启动.bat 启动，它会把错误留在窗口里。" ^
  "  Q: 浏览器没自动打开？" ^
  "  A: 手动访问终端里打印的 http://127.0.0.1:5000 即可。" ^
  "  Q: Windows 提示已保护你的电脑？" ^
  "  A: 点更多信息，再点仍要运行。这是因为 exe 没有代码签名。" ^
  "'@; Set-Content -LiteralPath 'dist\Image2Html\使用说明.txt' -Value $t -Encoding UTF8"
if errorlevel 1 echo       [警告] 说明文件生成失败，不影响 exe 使用。

echo       正在打包 zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Test-Path 'dist\Image2Html.zip') { Remove-Item 'dist\Image2Html.zip' -Force }; Compress-Archive -Path 'dist\Image2Html' -DestinationPath 'dist\Image2Html.zip' -Force"
if errorlevel 1 (
    echo       [警告] zip 打包失败，可手动压缩 dist\Image2Html 文件夹。
) else (
    echo       dist\Image2Html.zip 已生成，可直接发给别人。
)

echo.
echo ==========================================
echo   打包完成！
echo   输出目录：dist\Image2Html\
echo   入口文件：dist\Image2Html\Image2Html.exe
echo   分发压缩包：dist\Image2Html.zip
echo.
echo   分发给别人：直接把 dist\Image2Html.zip 发出去，
echo   对方解压后双击 Image2Html.exe 即可（无需 Python）。
echo ==========================================
echo.
pause
endlocal
