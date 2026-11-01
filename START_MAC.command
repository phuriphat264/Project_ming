#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo "  ระบบคำนวณต้นทุนและกำไร TikTok Shop (มาตัง คอสเมติก)"
echo "========================================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[!] ตรวจไม่พบ Python 3 ในเครื่องนี้ กรุณาติดตั้ง Python ก่อนใช้งาน"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[*] ตรวจพบการเปิดใช้งานครั้งแรก กำลังสร้าง Virtual Environment (.venv)..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "[OK] ติดตั้งสภาพแวดล้อมเสร็จสมบูรณ์!"
    echo ""
fi

source .venv/bin/activate
echo "[*] กำลังเปิดระบบคำนวณต้นทุน..."
open "http://localhost:8501" 2>/dev/null || true
streamlit run app.py --server.headless=true
