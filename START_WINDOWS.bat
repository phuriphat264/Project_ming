@echo off
cd /d "%~dp0"
cls

echo ========================================================
echo   Matang Cosmetic - Cost and Profit Analysis System
echo ========================================================
echo.

echo Checking Python installation...
py -3 --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYCMD=py -3
    goto :has_python
)

python --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYCMD=python
    goto :has_python
)

echo [ERROR] Python not found in this PC.
echo Please install Python 3.10+ from https://www.python.org/downloads/
echo.
pause
exit /b 1

:has_python
echo Python found!
echo.

if exist .venv\Scripts\python.exe goto :start_app

echo [*] First time setup: Creating Virtual Environment (.venv)...
%PYCMD% -m venv .venv

echo [*] Installing required packages from requirements.txt...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo [OK] Setup completed successfully!
echo.

:start_app
echo [*] Starting web application...
start "" http://localhost:8501
.venv\Scripts\python.exe -m streamlit run app.py --server.headless=true

echo.
pause
