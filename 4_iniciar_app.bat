@echo off
chcp 65001 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
start "" http://localhost:5000
python web_app.py
pause
