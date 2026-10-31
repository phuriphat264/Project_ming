from core.reloader import ensure_fresh

ensure_fresh()

import streamlit as st

from core import db
from core.ui import init_page, render_page_header, render_section_header, require_login

init_page("ผู้ใช้งาน", "⚙️")
me = require_login(admin_only=True)

render_page_header("จัดการผู้ใช้งานระบบ")

c_list, c_form = st.columns([1.2, 1], gap="medium")

with c_list:
    with st.container(border=True):
        render_section_header("รายชื่อผู้ใช้งาน", icon="👥")
        st.dataframe(
            db.list_users().rename(columns={"username": "ชื่อผู้ใช้", "role": "สิทธิ์", "display_name": "ชื่อที่แสดง"}),
            width="stretch",
            hide_index=True,
        )

        others = [u for u in db.list_users()["username"] if u != me["username"]]
        if others:
            col_del_sel, col_del_btn = st.columns([2, 1])
            target = col_del_sel.selectbox("เลือกผู้ใช้:", others, label_visibility="collapsed")
            if col_del_btn.button(f"🗑️ ลบ {target}", width="stretch"):
                db.delete_user(target)
                st.success(f"ลบ {target} แล้ว")
                st.rerun()

with c_form:
    with st.container(border=True):
        render_section_header("เพิ่มผู้ใช้ / เปลี่ยนรหัสผ่าน", icon="🔐")
        with st.form("user_form", clear_on_submit=True):
            username = st.text_input("ชื่อผู้ใช้ (Username) *")
            display = st.text_input("ชื่อ-นามสกุล / ตำแหน่ง")
            pw = st.text_input("รหัสผ่าน (อย่างน้อย 6 ตัวอักษร) *", type="password")
            role = st.selectbox(
                "สิทธิ์การใช้งาน",
                ["staff", "admin"],
                format_func=lambda r: "พนักงานทั่วไป (Staff)" if r == "staff" else "ผู้ดูแลระบบ / บัญชี (Admin)",
            )
            if st.form_submit_button("💾 บันทึก", type="primary", width="stretch"):
                if not username or len(pw) < 6:
                    st.error("กรุณากรอกชื่อผู้ใช้ และรหัสผ่านอย่างน้อย 6 ตัวอักษร")
                else:
                    db.upsert_user(username, pw, role, display)
                    st.success(f"บันทึก {username} เรียบร้อยแล้ว")
                    st.rerun()

st.divider()

# กล่องสำรองและกู้คืนข้อมูลระบบ (Data Backup & Restore)
with st.container(border=True):
    render_section_header("สำรองและกู้คืนฐานข้อมูลระบบ (One-Click Data Backup & Restore)", icon="💾")
    st.caption("แนะนำให้ดาวน์โหลดไฟล์สำรองเก็บไว้ใน Google Drive หรือ Flash Drive ทุกสิ้นเดือนเพื่อความปลอดภัยสูงสุด")
    b_col1, b_col2 = st.columns(2, gap="medium")
    with b_col1:
        st.markdown("##### 📦 1. ดาวน์โหลดไฟล์สำรองข้อมูลทั้งหมด")
        st.write("รวมฐานข้อมูล (`app.db`), ประวัติผลการคำนวณ (`snapshots`) และไฟล์ Excel ต้นฉบับทั้งหมด")
        backup_bytes = db.create_backup_zip_bytes()
        from datetime import datetime
        st.download_button(
            "⬇️ ดาวน์โหลด Backup ทั้งระบบ (.zip)",
            backup_bytes,
            file_name=f"Backup_Matang_Cosmetic_{datetime.now():%Y%m%d_%H%M%S}.zip",
            mime="application/zip",
            type="primary",
            width="stretch",
        )

    with b_col2:
        st.markdown("##### 🔄 2. กู้คืนข้อมูลจากไฟล์สำรอง")
        st.write("อัปโหลดไฟล์ Backup `.zip` เพื่อกู้คืนฐานข้อมูลและประวัติการคำนวณเดิม")
        restore_file = st.file_uploader("เลือกไฟล์ Backup (.zip)", type=["zip"], key="restore_zip_uploader")
        if restore_file is not None:
            if st.button("⚠️ ยืนยัน กู้คืนข้อมูลทับระบบปัจจุบัน", type="secondary", width="stretch"):
                with st.spinner("กำลังกู้คืนข้อมูล..."):
                    c_restored = db.restore_backup_from_zip(restore_file.getvalue())
                    st.success(f"กู้คืนข้อมูลสำเร็จ {c_restored} ไฟล์!")
                    st.rerun()

