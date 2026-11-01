@echo off
cd /d "%~dp0"
title Matang Cost Profit System

echo ========================================================
echo   Matang Cosmetic - Cost and Profit Analysis System
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in this PC.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo *IMPORTANT: Make sure to check "Add python.exe to PATH" during installation*
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [*] First time setup: Creating Virtual Environment (.venv)...
    python -m venv .venv
    echo [*] Installing required packages from requirements.txt...
    call .venv\Scripts\python.exe -m pip install --upgrade pip
    call .venv\Scripts\pip.exe install -r requirements.txt
    echo [OK] Setup completed successfully!
    echo.
)

echo [*] Starting web application...
start "" http://localhost:8501
call .venv\Scripts\python.exe -m streamlit run app.py --server.headless=true

pause
