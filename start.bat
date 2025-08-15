@echo off
setlocal

:: 启动 music_server.bat 并记录其进程ID
start /B "" cmd /c "music_server.bat & call set PID=!PID!"
set music_server_pid=%PID%

:: 启动 main.py
start "" python main.py

:: 等待用户关闭窗口
pause

:: 关闭 music_server.bat
taskkill /PID %music_server_pid% /F >nul 2>&1
endlocal