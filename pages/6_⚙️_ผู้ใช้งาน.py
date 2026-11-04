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
    c_s_list, c_s_form = st.columns([1.3, 1.1], gap="medium")
    shops_all = db.list_shops(active_only=False)

    with c_s_list:
        with st.container(border=True):
            render_section_header("รายชื่อช่องทาง TikTok Shop ทั้งหมด", icon="🏬")
            df_shops = pd.DataFrame(shops_all)
            if not df_shops.empty:
                df_shops["สถานะ"] = df_shops["is_active"].apply(lambda a: "🟢 เปิดใช้งาน" if a else "⚪ ปิดใช้งาน")
                df_shops["ประเภท"] = df_shops["is_default"].apply(lambda d: "★ ร้านหลัก" if d else "ร้านย่อย")
                show_df = df_shops[["code", "name", "tiktok_handle", "ประเภท", "สถานะ"]].rename(
                    columns={
                        "code": "รหัสร้าน",
                        "name": "ชื่อช่องทาง/ร้านค้า",
                        "tiktok_handle": "TikTok Handle",
                    }
                )
                st.dataframe(show_df, width="stretch", hide_index=True)

            st.markdown("###### ⚡ ทางลัดจัดการร้านค้าอย่างรวดเร็ว:")
            col_quick_sel, col_quick_edit, col_quick_star = st.columns([1.5, 1, 1])
            all_codes = [s["code"] for s in shops_all]
            quick_code = col_quick_sel.selectbox("เลือกร้านค้า:", options=all_codes, key="quick_shop_select_code")
            if col_quick_edit.button("✏️ แก้ไขร้านนี้", width="stretch", key="btn_quick_edit"):
                st.session_state["shop_mgmt_mode"] = "✏️ แก้ไขร้านค้าที่มีอยู่"
                st.session_state["editing_shop_code"] = quick_code
                st.rerun()

            curr_shop = next((s for s in shops_all if s["code"] == quick_code), None)
            is_already_def = curr_shop["is_default"] if curr_shop else False
            if col_quick_star.button("⭐ ตั้งเป็นร้านหลัก", width="stretch", disabled=is_already_def, key="btn_quick_star", help="ตั้งร้านนี้เป็นช่องทางเริ่มต้นของระบบ"):
                if curr_shop:
                    db.upsert_shop(curr_shop["code"], curr_shop["name"], curr_shop["tiktok_handle"], is_default=True, is_active=curr_shop["is_active"])
                    st.toast(f"ตั้ง {curr_shop['name']} เป็นร้านหลักแล้ว", icon="⭐")
                    st.rerun()

    with c_s_form:
        with st.container(border=True):
            mode = st.radio(
                "การทำงาน:",
                ["➕ เพิ่มร้านค้าใหม่", "✏️ แก้ไขร้านค้าที่มีอยู่"],
                index=1 if st.session_state.get("shop_mgmt_mode") == "✏️ แก้ไขร้านค้าที่มีอยู่" else 0,
                horizontal=True,
                key="radio_shop_mgmt_mode",
            )
            st.session_state["shop_mgmt_mode"] = mode

            if mode == "➕ เพิ่มร้านค้าใหม่":
                render_section_header("เพิ่มช่องทาง TikTok ใหม่", icon="➕")
                with st.form("form_add_shop", clear_on_submit=True):
                    s_code = st.text_input("รหัสร้าน (ภาษาอังกฤษตัวเล็ก เช่น live1, shop3) *", placeholder="เช่น live1").strip().lower()
                    s_name = st.text_input("ชื่อร้าน / ช่องทาง *", placeholder="เช่น มาตัง ไลฟ์สด 1").strip()
                    s_handle = st.text_input("TikTok Handle", placeholder="@matang_live").strip()
                    s_def = st.checkbox("ตั้งเป็นร้านหลัก (Default Shop)", value=False)
                    s_act = st.checkbox("เปิดใช้งาน (Active)", value=True)

                    if st.form_submit_button("➕ บันทึกร้านค้าใหม่", type="primary", width="stretch"):
                        if not s_code or not s_name:
                            st.error("⚠️ กรุณากรอกรหัสร้านและชื่อร้าน")
                        elif any(s["code"] == s_code for s in shops_all):
                            st.error(f"⚠️ รหัสร้าน '{s_code}' มีอยู่ในระบบแล้ว กรุณาใช้โหมดแก้ไขหรือเลือกรหัสอื่น")
                        else:
                            db.upsert_shop(s_code, s_name, s_handle, is_default=s_def, is_active=s_act)
                            st.success(f"เพิ่มช่องทาง {s_name} ({s_code}) เรียบร้อยแล้ว!")
                            st.rerun()

            else:
                render_section_header("แก้ไข / ลบข้อมูลช่องทาง TikTok", icon="✏️")
                all_codes = [s["code"] for s in shops_all]
                pre_sel = st.session_state.get("editing_shop_code")
                sel_idx = all_codes.index(pre_sel) if pre_sel in all_codes else 0
                edit_code = st.selectbox("เลือกร้านค้าที่ต้องการแก้ไข:", options=all_codes, index=sel_idx, key="sel_shop_to_edit")
                st.session_state["editing_shop_code"] = edit_code
                shop_data = next((s for s in shops_all if s["code"] == edit_code), shops_all[0])

                with st.form("form_edit_shop"):
                    st.text_input("รหัสร้าน (Code - ไม่สามารถเปลี่ยนได้)", value=shop_data["code"], disabled=True)
                    e_name = st.text_input("ชื่อร้าน / ช่องทาง *", value=shop_data["name"]).strip()
                    e_handle = st.text_input("TikTok Handle", value=shop_data["tiktok_handle"]).strip()
                    e_def = st.checkbox("ตั้งเป็นร้านหลัก (Default Shop)", value=bool(shop_data["is_default"]))
                    e_act = st.checkbox("เปิดใช้งาน (Active)", value=bool(shop_data["is_active"]))

                    c_b_save, c_b_cancel = st.columns([2, 1], gap="small")
                    with c_b_save:
                        btn_save = st.form_submit_button("💾 บันทึกการแก้ไข", type="primary", width="stretch")
                    with c_b_cancel:
                        btn_cancel = st.form_submit_button("✖️ ยกเลิก", width="stretch")

                    if btn_save:
                        if not e_name:
                            st.error("⚠️ กรุณาระบุชื่อร้าน")
                        else:
                            db.upsert_shop(shop_data["code"], e_name, e_handle, is_default=e_def, is_active=e_act)
                            st.success(f"อัปเดตข้อมูลร้าน {e_name} สำเร็จแล้ว!")
                            st.rerun()

                    if btn_cancel:
                        st.session_state["shop_mgmt_mode"] = "➕ เพิ่มร้านค้าใหม่"
                        st.session_state.pop("editing_shop_code", None)
                        st.rerun()

                # ปุ่มลบแยกออกมาพร้อมยืนยันความปลอดภัย
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                is_current_default = bool(shop_data.get("is_default"))
                is_only_shop = len(shops_all) <= 1
                if is_current_default:
                    st.info("ℹ️ ร้านนี้ถูกตั้งเป็น **'ร้านหลัก'** อยู่ จึงไม่สามารถลบได้ หากต้องการลบ กรุณาตั้งร้านอื่นเป็นร้านหลักก่อน")
                elif is_only_shop:
                    st.info("ℹ️ ระบบต้องมีร้านค้าเหลืออยู่อย่างน้อย 1 ร้าน จึงไม่สามารถลบได้")
                else:
                    with st.expander(f"🗑️ ลบช่องทาง '{shop_data['name']}'", expanded=False):
                        st.warning(f"⚠️ คุณแน่ใจหรือไม่ว่าต้องการลบช่องทาง **{shop_data['name']} (`{shop_data['code']}`)**? (การลบนี้ไม่สามารถย้อนคืนได้)")
                        if st.button(f"ยืนยันการลบช่องทาง {shop_data['code']}", type="secondary", width="stretch", key=f"btn_del_shop_{shop_data['code']}"):
                            if db.delete_shop(shop_data["code"]):
                                st.success(f"ลบช่องทาง {shop_data['name']} เรียบร้อยแล้ว")
                                st.session_state["shop_mgmt_mode"] = "➕ เพิ่มร้านค้าใหม่"
                                st.session_state.pop("editing_shop_code", None)
                                st.rerun()
                            else:
                                st.error("ไม่สามารถลบช่องทางนี้ได้ กรุณาตรวจสอบว่าไม่ได้เป็นร้านหลัก")

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

