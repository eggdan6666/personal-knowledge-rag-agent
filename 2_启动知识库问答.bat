@echo off
chcp 65001 >nul
title 个人知识库 RAG Agent - 智能问答
echo ========================================================
echo    欢迎使用【个人知识库 RAG Agent】智能问答系统！
echo    输入您的问题后按回车，输入 exit 或 退出 即可离开。
echo ========================================================
echo.
cd /d "%~dp0knowledge-agent"

:: 检查 Python 运行环境
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "C:\Users\ZhuanZ\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=C:\Users\ZhuanZ\AppData\Local\Programs\Python\Python311\python.exe"
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未在系统 PATH 中找到 Python 命令！
    echo 请确认已安装 Python 3.10+ 并勾选了 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

"%PYTHON_CMD%" query.py
pause
