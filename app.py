"""หน้าหลัก — เรียบง่าย ตัวใหญ่ กดเข้าทำงานได้ทันที"""
from core.reloader import ensure_fresh

ensure_fresh()

import streamlit as st

from core import db
from core.pipeline import ALL_PERIODS_KEY
from core.ui import (
    baht,
    init_page,
    load_period_result,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
    summarize_for_period,
)

init_page("หน้าหลัก", "🏠")
user = require_login()

skus = db.get_skus()
snapshots = db.list_snapshots()
latest_period = snapshots.iloc[0]["month"] if not snapshots.empty else None
active_period = st.session_state.get("period", latest_period or "-")

render_page_header(
    title="🏠 ระบบคำนวณต้นทุนและกำไรอัตโนมัติ",
    subtitle="บริษัท มาตัง คอสเมติก จำกัด",
    period=active_period,
)

total_periods = len(snapshots)
if not snapshots.empty and user["role"] == "admin":
    all_res = load_period_result(ALL_PERIODS_KEY)
    all_sum = summarize_for_period(all_res, ALL_PERIODS_KEY) if all_res is not None else None
    all_sales = all_sum.net_sales if all_sum else 0.0
    all_profit = all_sum.net_profit if all_sum else 0.0
else:
    all_sales = 0.0
    all_profit = 0.0

c1, c2, c3 = st.columns(3)
with c1:
    render_kpi_card("สินค้าในระบบทั้งหมด", f"{len(skus):,} รายการ", f"บันทึกข้อมูลแล้ว {total_periods:,} งวด", icon="📦")
with c2:
    render_kpi_card(
        f"รายได้รวมทุกงวด ({total_periods} งวด)" if total_periods > 0 else "รายได้รวมทุกงวด",
        baht(all_sales) if (total_periods > 0 and user["role"] == "admin") else "-",
        f"งวดล่าสุด: {latest_period or '-'}",
        icon="💰",
    )
with c3:
    render_kpi_card(
        f"กำไรสุทธิรวมทุกงวด ({total_periods} งวด)" if total_periods > 0 else "กำไรสุทธิรวมทุกงวด",
        baht(all_profit) if (total_periods > 0 and user["role"] == "admin") else "-",
        delta_positive=all_profit >= 0,
        icon="📈",
    )

render_section_header("เลือกเมนูที่ต้องการทำงาน", icon="👉")

m1, m2, m3 = st.columns(3)
with m1:
    with st.container(border=True):
        st.markdown("### 📤 1. นำเข้าไฟล์ Excel")
        st.write("โยนไฟล์เดียวหรือหลายเดือนพร้อมกัน คำนวณและบันทึกอัตโนมัติ")
        st.page_link("pages/2_📤_นำเข้าข้อมูล.py", label="ไปหน้านำเข้าข้อมูล →", icon="📤", width="stretch")

if user["role"] == "admin":
    with m2:
        with st.container(border=True):
            st.markdown("### 📦 2. แก้ไขราคาทุนสินค้า")
            st.write("เพิ่ม/ลบ/แก้ไขราคาทุน SKU และค่าใช้จ่ายรายเดือน")
            st.page_link("pages/3_📦_สินค้าและต้นทุน.py", label="ไปหน้าจัดการสินค้า →", icon="📦", width="stretch")

    with m3:
        with st.container(border=True):
            st.markdown("### 📊 3. ดูแยกเดือน & สรุปทั้งหมด")
            st.write("สลับดูรายเดือน เปรียบเทียบทุกงวด และดาวน์โหลด Excel")
            st.page_link("pages/1_📊_แดชบอร์ด.py", label="ไปหน้าแดชบอร์ด →", icon="📊", width="stretch")
