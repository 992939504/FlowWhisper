@echo off
echo ========================================
echo     启动 FlowWhisper 转录工具
echo ========================================
echo.

echo 正在检查依赖...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo [信息] Python环境检查通过
echo.

echo 启动图形界面...
python all_in_one_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 程序启动失败
    echo 可能的原因：
    echo 1. 缺少依赖库 - 请运行 install_dependencies.bat
    echo 2. 缺少whisper-cli.exe - 请下载whisper.cpp
    echo 3. 缺少模型文件 - 请下载Whisper模型
    echo.
    pause
)

echo.
echo 程序已退出
pause