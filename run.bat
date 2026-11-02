@echo off
chcp 65001 >nul
title TikTok Shop Cost & Profit Analysis System
cls

echo ================================================================
echo   TikTok Shop Cost & Profit Analysis System
echo   ระบบวิเคราะห์ต้นทุนและกำไร TikTok Shop (D-VINE)
echo ================================================================
echo.

:: 1. ตรวจสอบ Python ในเครื่อง
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ไม่พบ Python ในระบบ!
    echo กรุณาติดตั้ง Python 3.10 ขึ้นไปจาก https://www.python.org/downloads/
    echo และอย่าลืมติ๊กถูก "Add Python to PATH" ตอนติดตั้ง
    echo.
    pause
    exit /b 1
)

:: 2. ตรวจสอบและสร้าง Virtual Environment (.venv)
if not exist ".venv" (
    echo [*] กำลังสร้าง Virtual Environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] สร้าง .venv ไม่สำเร็จ
        pause
        exit /b 1
    )
    echo [*] ติดตั้งแพ็กเกจที่จำเป็นจาก requirements.txt...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

:: 3. ตรวจสอบ streamlit ว่าติดตั้งแล้วหรือยัง
python -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] กำลังติดตั้ง Dependencies...
    pip install -r requirements.txt
)

echo.
echo ================================================================
echo   [OK] เริ่มต้นระบบ... กำลังเปิดเว็บเบราว์เซอร์
echo   (สามารถกด Ctrl+C ในหน้าต่างนี้เพื่อหยุดการทำงาน)
echo ================================================================
echo.

:: 4. เปิดโปรแกรมด้วย Streamlit
streamlit run app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] โปรแกรมปิดตัวลงเนื่องจากเกิดข้อผิดพลาด
    pause
)
