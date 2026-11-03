from core.ui import init_page

init_page("การตั้งค่าระบบ", "⚙️")

from core.reloader import ensure_fresh

ensure_fresh()

import pandas as pd
import streamlit as st

from core import db
from core.ui import render_page_header, render_section_header, require_login

me = require_login(admin_only=True)

render_page_header("การตั้งค่าระบบและจัดการช่องทาง")

tab_shops, tab_users, tab_backup = st.tabs(
    [
        "🏬 ช่องทาง TikTok Shop (Channels / Shops)",
        "👥 จัดการผู้ใช้งานระบบ (User Accounts)",
        "💾 สำรองและกู้คืนฐานข้อมูล (Backup & Restore)",
    ]
)

# ==============================================================================
# แท็บที่ 1: จัดการช่องทาง TikTok Shop
# ==============================================================================
with tab_shops:
    c_s_list, c_s_form = st.columns([1.3, 1], gap="medium")
    shops_all = db.list_shops(active_only=False)

    with c_s_list:
        with st.container(border=True):
            render_section_header("รายชื่อช่องทาง TikTok Shop ทั้งหมด", icon="🏬")
            df_shops = pd.DataFrame(shops_all)
            if not df_shops.empty:
                df_shops["สถานะ"] = df_shops["is_active"].apply(lambda a: "🟢 เปิดใช้งาน" if a else "⚪ ปิด")
                df_shops["ประเภท"] = df_shops["is_default"].apply(lambda d: "★ ช่องทางหลัก" if d else "ช่องทางย่อย")
                show_df = df_shops[["code", "name", "tiktok_handle", "ประเภท", "สถานะ"]].rename(
                    columns={
                        "code": "รหัสร้าน",
                        "name": "ชื่อช่องทาง/ร้านค้า",
                        "tiktok_handle": "TikTok Handle",
                    }
                )
                st.dataframe(show_df, width="stretch", hide_index=True)

            del_candidates = [s["code"] for s in shops_all if s["code"] not in ("matang",)]
            if del_candidates:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                col_d_sel, col_d_btn = st.columns([2, 1])
                target_shop = col_d_sel.selectbox("เลือกร้านที่ต้องการลบ:", del_candidates, label_visibility="collapsed")
                if col_d_btn.button(f"🗑️ ลบ {target_shop}", width="stretch"):
                    if db.delete_shop(target_shop):
                        st.success(f"ลบช่องทาง {target_shop} เรียบร้อยแล้ว")
                        st.rerun()

    with c_s_form:
        with st.container(border=True):
            render_section_header("เพิ่ม / แก้ไขช่องทาง TikTok", icon="➕")
            with st.form("form_shop_mgmt", clear_on_submit=True):
                s_code = st.text_input("รหัสร้าน (ภาษาอังกฤษตัวเล็ก เช่น matang, dwine, live1) *").strip().lower()
                s_name = st.text_input("ชื่อร้าน / ช่องทาง (เช่น มาตัง คอสเมติก, ดีไวน์ Thailand) *").strip()
                s_handle = st.text_input("TikTok Handle (เช่น @matang_official)").strip()
                s_def = st.checkbox("ตั้งเป็นร้านหลัก (Default Shop)", value=False)
                s_act = st.checkbox("เปิดใช้งาน (Active)", value=True)

                if st.form_submit_button("💾 บันทึกช่องทาง", type="primary", width="stretch"):
                    if not s_code or not s_name:
                        st.error("กรุณากรอกรหัสร้านและชื่อร้าน")
                    else:
                        db.upsert_shop(s_code, s_name, s_handle, is_default=s_def, is_active=s_act)
                        st.success(f"บันทึกช่องทาง {s_name} ({s_code}) เรียบร้อยแล้ว")
                        st.rerun()

# ==============================================================================
# แท็บที่ 2: จัดการผู้ใช้งานระบบ
# ==============================================================================
with tab_users:
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

# ==============================================================================
# แท็บที่ 3: สำรองและกู้คืนฐานข้อมูล
# ==============================================================================
with tab_backup:
    with st.container(border=True):
        render_section_header("สำรองและกู้คืนฐานข้อมูลระบบ (One-Click Data Backup & Restore)", icon="💾")
        st.caption("แนะนำให้ดาวน์โหลดไฟล์สำรองเก็บไว้ใน Google Drive หรือ Flash Drive ทุกสิ้นเดือนเพื่อความปลอดภัยสูงสุด")
        b_col1, b_col2 = st.columns(2, gap="medium")
        with b_col1:
            st.markdown("##### 📦 1. ดาวน์โหลดไฟล์สำรองข้อมูลทั้งหมด")
            st.write("รวมฐานข้อมูล (`app.db`), ช่องทางร้านค้า, ประวัติผลการคำนวณ (`snapshots`) และไฟล์ Excel ทั้งหมด")
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

