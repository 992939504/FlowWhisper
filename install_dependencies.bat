@echo off
echo ========================================
echo    音频转录全功能工具依赖安装脚本
echo ========================================
echo.

echo 正在检查Python环境...
python --version
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo.
echo [信息] Python环境检查通过
echo.

echo 正在升级pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [警告] pip升级失败，但可以继续安装
)

echo.
echo 正在安装核心依赖库...
echo.

echo 安装 numpy...
pip install numpy>=1.21.0
if errorlevel 1 (
    echo [错误] numpy安装失败
    pause
    exit /b 1
)

echo 安装 scipy...
pip install scipy>=1.7.0
if errorlevel 1 (
    echo [错误] scipy安装失败
    pause
    exit /b 1
)

echo 安装 openai...
pip install openai>=1.100.0
if errorlevel 1 (
    echo [错误] openai安装失败
    pause
    exit /b 1
)

echo.
echo 正在安装音频处理库...
echo.

echo 安装 pydub...
pip install pydub>=0.25.1
if errorlevel 1 (
    echo [错误] pydub安装失败
    pause
    exit /b 1
)

echo 安装 sounddevice...
pip install sounddevice>=0.4.5
if errorlevel 1 (
    echo [错误] sounddevice安装失败
    pause
    exit /b 1
)

echo.
echo 正在安装系统交互库...
echo.

echo 安装 pyperclip...
pip install pyperclip>=1.8.0
if errorlevel 1 (
    echo [错误] pyperclip安装失败
    pause
    exit /b 1
)

echo 安装 pynput...
pip install pynput>=1.7.0
if errorlevel 1 (
    echo [错误] pynput安装失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo           依赖安装完成！
echo ========================================
echo.
echo 所有必需的依赖库已成功安装。
echo.
echo 使用说明：
echo 1. 运行 python all_in_one_gui.py 启动完整功能GUI
echo 2. 运行 python transcribe_gui.py 启动基础转录GUI
echo 3. 确保 whisper 目录中有 whisper-cli.exe 和模型文件
echo 4. 在智能音频清理功能中配置您的AI API信息
echo.
echo 按任意键退出...
pause >nul