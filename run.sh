#!/bin/bash
# สคริปต์เปิดระบบคำนวณต้นทุนและกำไรอัตโนมัติ (macOS / Linux)
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "กำลังเตรียมสภาพแวดล้อม Python..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

echo "=================================================="
echo "  ระบบคำนวณต้นทุนและกำไรอัตโนมัติ"
echo "  บริษัท มาตัง คอสเมติก จำกัด"
echo "=================================================="
echo "กำลังเปิดระบบ..."
echo "บัญชีเริ่มต้น:"
echo "  - ผู้บริหาร: admin / admin123"
echo "  - พนักงาน: staff / staff123"
echo "--------------------------------------------------"

.venv/bin/streamlit run app.py --server.headless=false
