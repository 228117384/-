@echo off
chcp 65001 > nul
title 安装Python依赖库

echo 正在安装Python依赖库...
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到Python，请先安装Python 3.7或更高版本
    echo 可以从 https://www.python.org/downloads/ 下载
    pause
    exit /b
)

:: 检查pip是否可用
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: pip包管理器不可用，请确保Python安装正确
    pause
    exit /b
)

:: 使用国内镜像源加速下载
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo 安装失败，请检查网络连接或手动安装依赖
    echo 可以尝试运行: pip install -r requirements.txt
    pause
    exit /b
)

echo.
echo 依赖库安装成功!
echo.
echo 注意: 此程序需要FFmpeg支持视频功能
echo 请从 https://ffmpeg.org/download.html 下载FFmpeg
echo 解压后将bin目录添加到系统PATH环境变量
echo.
echo 按任意键退出...
pause > nul