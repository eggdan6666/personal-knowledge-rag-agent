# -*- coding: utf-8 -*-
"""一键修复或重新生成 Windows 批处理启动脚本（以 UTF-8 编码写入并配置 chcp 65001）。"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

bat_ingest = """@echo off
chcp 65001 >nul
title 个人知识库 RAG Agent - 文档导入
echo ========================================================
echo    正在扫描并导入【输出资料存放处】中的所有文档...
echo    支持格式：PDF / DOCX / TXT
echo ========================================================
echo.
cd /d "%~dp0knowledge-agent"

:: 检查 Python 运行环境
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
) else if exist "%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe"
) else if exist "C:\\Users\\ZhuanZ\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" (
    set "PYTHON_CMD=C:\\Users\\ZhuanZ\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"
)

if "%PYTHON_CMD%"=="" (
    echo [错误] 未在系统 PATH 中找到 Python 命令！
    echo 请确认已安装 Python 3.10+ 并勾选了 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

"%PYTHON_CMD%" ingest.py
echo.
echo ========================================================
echo    导入完成！您可以双击【2_启动知识库问答.bat】开始提问。
echo ========================================================
pause
"""

bat_query = """@echo off
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
) else if exist "%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe"
) else if exist "C:\\Users\\ZhuanZ\\AppData\\Local\\Programs\\Python\\Python311\\python.exe" (
    set "PYTHON_CMD=C:\\Users\\ZhuanZ\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"
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
"""

with open(os.path.join(BASE_DIR, "1_导入文档入库.bat"), "w", encoding="utf-8") as f:
    f.write(bat_ingest)

with open(os.path.join(BASE_DIR, "2_启动知识库问答.bat"), "w", encoding="utf-8") as f:
    f.write(bat_query)

print("Batch files successfully written in UTF-8 with chcp 65001!")
