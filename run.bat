@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==================================================
echo   ระบบคำนวณต้นทุนและกำไรอัตโนมัติ
echo   บริษัท มาตัง คอสเมติก จำกัด
echo ==================================================
echo บัญชีเริ่มต้น:
echo   - ผู้บริหาร: admin / admin123
echo   - พนักงาน: staff / staff123
echo --------------------------------------------------

if not exist ".venv" (
    echo กำลังเตรียมสภาพแวดล้อม Python...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

streamlit run app.py
pause
