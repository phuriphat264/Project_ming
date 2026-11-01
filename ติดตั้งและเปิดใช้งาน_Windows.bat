@echo off
chcp 65001 >nul
title ระบบคำนวณต้นทุนและกำไร - บริษัท มาตัง คอสเมติก จำกัด

echo ========================================================
echo   ระบบคำนวณต้นทุนและกำไร TikTok Shop (มาตัง คอสเมติก)
echo ========================================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] ตรวจไม่พบ Python ในเครื่องนี้
    echo     กรุณาดาวน์โหลดและติดตั้ง Python 3.10+ จาก https://www.python.org/downloads/
    echo     *ข้อสำคัญ: อย่าลืมติ๊กถูก "Add python.exe to PATH" ตอนติดตั้งด้วยครับ*
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [*] ตรวจพบการเปิดใช้งานครั้งแรก กำลังสร้าง Virtual Environment (.venv)...
    python -m venv .venv
    echo [*] กำลังติดตั้งไลบรารีที่จำเป็นจาก requirements.txt (ใช้เวลาประมาณ 1-2 นาที)...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo [OK] ติดตั้งสภาพแวดล้อมเสร็จสมบูรณ์!
    echo.
)

echo [*] กำลังเปิดระบบคำนวณต้นทุน...
call .venv\Scripts\activate.bat
start "" http://localhost:8501
streamlit run app.py --server.headless=true

pause
