from core.ui import init_page

init_page("สินค้าและต้นทุน", "📦")

from core.reloader import ensure_fresh

ensure_fresh()

from datetime import date
import html
from io import BytesIO

import pandas as pd
import streamlit as st

from core import db
from core.loader import load_workbook
from core.pipeline import ALL_PERIODS_KEY
from core.ui import (
    baht,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
)

require_login(admin_only=True)

render_page_header("จัดการตาราง SKU (ราคาทุน / ปลีก / โปร / ตั้งขาย) และค่าใช้จ่ายรายเดือน", period=st.session_state.get("period"))


def _clear_export_caches() -> None:
    st.session_state.pop("_cached_master_excel_key", None)
    st.session_state.pop("_cached_master_excel_bytes", None)
    st.session_state.pop("_cached_rep_key", None)
    st.session_state.pop("_cached_rep_master_xlsx", None)
    st.session_state.pop("_cached_rep_xlsx", None)


# ==================== DIALOGS: SKU ====================
@st.dialog("✏️ แก้ไขข้อมูลสินค้า (SKU)", width="large")
def edit_sku_dialog(row: dict) -> None:
    st.markdown(
        f'<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;padding:12px 16px;margin-bottom:16px;">'
        f'<span style="font-size:1rem;color:#64748b;">รหัส:</span> '
        f'<b style="font-size:1.25rem;color:#0f172a;">{row["sku"]}</b>'
        f"</div>",
        unsafe_allow_html=True,
    )
    with st.form("edit_sku_form"):
        c_n, c_cat = st.columns([2, 1])
        name = c_n.text_input("ชื่อ", value=str(row.get("name", "")))
        cat = c_cat.text_input("หมวดหมู่ (ถ้ามี)", value=str(row.get("category", "")))

        p1, p2, p3, p4 = st.columns(4)
        cost = p1.number_input("ราคาทุน (บาท) *", min_value=0.0, value=float(row.get("unit_cost", 0.0)), step=1.0, format="%.2f")
        retail = p2.number_input("ราคาปลีก (บาท)", min_value=0.0, value=float(row.get("retail_price", 0.0)), step=1.0, format="%.2f")
        promo = p3.number_input("ราคาโปร (บาท)", min_value=0.0, value=float(row.get("promo_price", 0.0)), step=1.0, format="%.2f")
        list_p = p4.number_input("ราคาตั้งขาย (บาท)", min_value=0.0, value=float(row.get("list_price", 0.0)), step=1.0, format="%.2f")

        b1, b2 = st.columns([2, 1])
        save_clicked = b1.form_submit_button("💾 บันทึกการแก้ไข", type="primary", width="stretch")
        delete_clicked = b2.form_submit_button("🗑️ ลบสินค้านี้", type="secondary", width="stretch")

        if save_clicked:
            db.upsert_skus(
                pd.DataFrame(
                    [
                        {
                            "sku": row["sku"],
                            "name": name.strip(),
                            "category": cat.strip(),
                            "unit_cost": cost,
                            "retail_price": retail,
                            "promo_price": promo,
                            "list_price": list_p,
                        }
                    ]
                )
            )
            _clear_export_caches()
            st.toast(f"บันทึก {row['sku']} เรียบร้อยแล้ว")
            st.rerun()

        if delete_clicked:
            db.delete_sku(row["sku"])
            _clear_export_caches()
            st.toast(f"ลบ {row['sku']} เรียบร้อยแล้ว")
            st.rerun()


@st.dialog("➕ เพิ่มสินค้าใหม่ (SKU)", width="large")
def add_sku_dialog() -> None:
    with st.form("add_sku_modal_form"):
        c1, c2 = st.columns([1, 1.8])
        sku = c1.text_input("รหัส *", placeholder="เช่น FZQCS004002")
        name = c2.text_input("ชื่อ *", placeholder="เช่น โปรเปย์เดย์ โดสไฮโดร 100 ml. 2 ขวด")
        cat = st.text_input("หมวดหมู่ (ถ้ามี)", placeholder="เช่น ครีมบำรุงผิวกายและโลชั่น")

        p1, p2, p3, p4 = st.columns(4)
        cost = p1.number_input("ราคาทุน (บาท) *", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        retail = p2.number_input("ราคาปลีก (บาท)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        promo = p3.number_input("ราคาโปร (บาท)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        list_p = p4.number_input("ราคาตั้งขาย (บาท)", min_value=0.0, value=0.0, step=1.0, format="%.2f")

        if st.form_submit_button("💾 บันทึกสินค้าใหม่", type="primary", width="stretch"):
            if not sku.strip():
                st.error("กรุณากรอกรหัส SKU")
            else:
                db.upsert_skus(
                    pd.DataFrame(
                        [
                            {
                                "sku": sku.strip(),
                                "name": name.strip(),
                                "category": cat.strip(),
                                "unit_cost": cost,
                                "retail_price": retail,
                                "promo_price": promo,
                                "list_price": list_p,
                            }
                        ]
                    )
                )
                _clear_export_caches()
                st.toast(f"เพิ่มสินค้า {sku.strip()} เรียบร้อยแล้ว")
                st.rerun()


@st.dialog("⚠️ ยืนยันการลบข้อมูลต้นทุนทั้งหมด")
def clear_all_skus_dialog(count: int) -> None:
    st.warning(f"ต้องการลบข้อมูลสินค้าและราคาทุนทั้งหมด **{count:,} รายการ** ออกจากระบบใช่หรือไม่?")
    c1, c2 = st.columns(2)
    if c1.button("🗑️ ยืนยัน ลบทั้งหมด", type="primary", width="stretch"):
        db.clear_all_skus()
        st.toast("ลบข้อมูลต้นทุนสินค้าทั้งหมดเรียบร้อยแล้ว")
        st.rerun()
    if c2.button("ยกเลิก", type="secondary", width="stretch"):
        st.rerun()


# ==================== DIALOGS: MONTHLY EXPENSES ====================
@st.dialog("➕ เพิ่มรายการค่าใช้จ่ายโรงงาน", width="large")
def add_expense_dialog(month: str) -> None:
    st.caption(f"งวดเดือน: **{month}** (เช่น ค่าแรง, ค่าไฟ, ค่าน้ำ, ค่ากล่องพัสดุ, ค่าเช่า ฯลฯ)")
    with st.form("add_exp_form"):
        item = st.text_input("ชื่อรายการค่าใช้จ่าย *", placeholder="เช่น ค่ากล่องและบับเบิ้ลกันกระแทก")
        amount = st.number_input("จำนวนเงินต่อเดือน (บาท) *", min_value=0.0, value=0.0, step=500.0, format="%.2f")
        if st.form_submit_button("💾 เพิ่มรายการค่าใช้จ่าย", type="primary", width="stretch"):
            if not item.strip():
                st.error("กรุณากรอกชื่อรายการค่าใช้จ่าย")
            else:
                db.upsert_fixed_cost_item(month, item.strip(), amount)
                st.toast(f"เพิ่ม '{item.strip()}' ในงวด {month} แล้ว")
                st.rerun()


@st.dialog("✏️ แก้ไข / ลบ รายการค่าใช้จ่าย", width="large")
def edit_expense_dialog(month: str, old_item: str, old_amount: float) -> None:
    st.caption(f"งวดเดือน: **{month}**")
    with st.form("edit_exp_form"):
        item = st.text_input("ชื่อรายการค่าใช้จ่าย *", value=old_item)
        amount = st.number_input("จำนวนเงินต่อเดือน (บาท) *", min_value=0.0, value=float(old_amount), step=500.0, format="%.2f")
        b1, b2 = st.columns([2, 1])
        save_btn = b1.form_submit_button("💾 บันทึกการแก้ไข", type="primary", width="stretch")
        del_btn = b2.form_submit_button("🗑️ ลบรายการนี้", type="secondary", width="stretch")
        if save_btn:
            if not item.strip():
                st.error("กรุณากรอกชื่อรายการค่าใช้จ่าย")
            else:
                db.upsert_fixed_cost_item(month, item.strip(), amount, old_item=old_item)
                st.toast(f"อัปเดต '{item.strip()}' แล้ว")
                st.rerun()
        if del_btn:
            db.delete_fixed_cost_item(month, old_item)
            st.toast(f"ลบ '{old_item}' แล้ว")
            st.rerun()


# ==================== SUMMARY CARDS ====================
skus = db.get_skus()
ready_cnt = int((skus["unit_cost"] > 0).sum())
missing_cnt = len(skus) - ready_cnt

all_months = db.list_expense_months()
raw_session_p = st.session_state.get("period")
default_month = (
    raw_session_p
    if (raw_session_p and raw_session_p != ALL_PERIODS_KEY)
    else (all_months[0] if all_months else f"{date.today():%Y-%m}")
)
if default_month not in all_months:
    all_months = [default_month] + all_months

k1, k2, k3 = st.columns(3, gap="medium")
with k1:
    render_kpi_card("สินค้าในระบบทั้งหมด (SKU)", f"{len(skus):,} รายการ", f"มีราคาทุนแล้ว {ready_cnt:,} รายการ", icon="📦")
with k2:
    render_kpi_card("สินค้าที่ยังไม่มีราคาทุน", f"{missing_cnt:,} รายการ", "กดแก้ไขเพื่อใส่ราคาทุน" if missing_cnt > 0 else "ครบทุกตัวแล้ว", icon="✅" if missing_cnt == 0 else "⚠️")
with k3:
    render_kpi_card(
        f"ค่าใช้จ่ายโรงงาน ({default_month})",
        baht(db.total_fixed_cost(default_month)),
        f"ค่าคอมคนขาย {db.get_comm_pct(default_month):.0f}%",
        icon="🏭",
    )

tab_sku, tab_fixed, tab_mappings, tab_bulk = st.tabs(
    [
        "📋 1. ตาราง SKU (รหัส / ชื่อ / ราคาทุน / ปลีก / โปร / ตั้งขาย)",
        "🏭 2. ค่าแรง / ค่าน้ำ / ค่าไฟ / ค่าคอมฯ",
        "🔗 3. จับคู่ชื่อสินค้ากับ SKU (TikTok Name ↔ SKU)",
        "📥 4. นำเข้า / ส่งออกชีต SKU",
    ]
)

# ==================== TAB 1: SKU MASTER ====================
with tab_sku:
    with st.container(border=True):
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #eff6ff 0%, #e0e7ff 100%); border: 1px solid #c7d2fe; border-radius: 14px; padding: 14px 18px; margin-bottom: 16px;">
                <div style="font-size: 1.02rem; font-weight: 800; color: #1e1b4b; display: flex; align-items: center; gap: 8px;">
                    💡 วิธีใช้งานตาราง SKU & ความหมายของราคาทุน:
                </div>
                <div style="font-size: 0.92rem; color: #3730a3; margin-top: 4px; line-height: 1.55;">
                    • <b>ราคาทุน (คอลัมน์สีแดง/ดำ):</b> ทุนจริงของสินค้าต่อ 1 ชิ้น ที่ระบบจะนำไปคูณจำนวนขายจริงเพื่อคิดต้นทุน (Col G) และกำไรสุทธิ (Col H)<br>
                    • <b>กดปุ่ม ✏️ แก้ไข:</b> แก้ไขราคาทุนหรือชื่อสินค้า | <b>กด ➕ เพิ่มสินค้าใหม่:</b> เพื่อใส่สินค้าตัวใหม่เข้าระบบ
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        f1, f2, f3, f4 = st.columns([2.1, 1.1, 1.0, 1.0], gap="small")
        q = f1.text_input("ค้นหา", label_visibility="collapsed", placeholder="🔎 ค้นหารหัส, ชื่อ หรือหมวดหมู่...")
        only_missing = f2.checkbox("เฉพาะที่ยังไม่มีราคาทุน")
        if f3.button("➕ เพิ่มสินค้าใหม่", type="primary", width="stretch"):
            add_sku_dialog()
        if f4.button("🗑️ ลบต้นทุนทั้งหมด", type="secondary", width="stretch", disabled=skus.empty):
            clear_all_skus_dialog(len(skus))

        view = skus.copy()
        if q:
            mask = view[["sku", "name", "category"]].apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
            view = view[mask]
        if only_missing:
            view = view[view["unit_cost"] <= 0]

        st.markdown(
            '<div style="background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);border:1px solid #e2e8f0;'
            'border-radius:12px;padding:14px 16px;margin:12px 0 8px 0;font-size:0.95rem;font-weight:800;color:#475569;'
            'text-transform:uppercase;letter-spacing:0.02em;'
            'display:grid;grid-template-columns:1.25fr 2.4fr 0.9fr 0.85fr 0.85fr 0.9fr 0.75fr 0.55fr;gap:8px;align-items:center;">'
            "<div>รหัส SKU</div><div>ชื่อสินค้า</div>"
            '<div style="text-align:right;">ราคาทุน</div>'
            '<div style="text-align:right;">ราคาปลีก</div>'
            '<div style="text-align:right;">ราคาโปร</div>'
            '<div style="text-align:right;">ราคาตั้งขาย</div>'
            '<div style="text-align:center;">แก้ไข</div><div style="text-align:center;">ลบ</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        if view.empty:
            st.info("ยังไม่มีข้อมูลสินค้าในระบบ (กด ➕ เพิ่มสินค้าใหม่ หรืออัปโหลดไฟล์ Excel ที่มีชีต SKU)")
        else:
            total_items = len(view)
            page_size = 20
            total_pages = max(1, (total_items + page_size - 1) // page_size)

            cur_page = st.session_state.get("sku_page_num", 1)
            if cur_page > total_pages:
                cur_page = 1
                st.session_state["sku_page_num"] = 1

            start_idx = (cur_page - 1) * page_size
            page_slice = view.iloc[start_idx : start_idx + page_size]

            with st.container(height=520, border=False):
                for _, r in page_slice.iterrows():
                    cols = st.columns([1.25, 2.4, 0.9, 0.85, 0.85, 0.9, 0.75, 0.55])
                    cols[0].markdown(f"<div style='font-size:1.02rem;font-weight:600;padding-top:8px;'>{html.escape(str(r['sku']))}</div>", unsafe_allow_html=True)
                    cols[1].markdown(f"<div style='font-size:1.02rem;color:#0f172a;padding-top:8px;'>{html.escape(str(r['name'] or '-'))}</div>", unsafe_allow_html=True)
                    cost_color = "#dc2626" if r["unit_cost"] <= 0 else "#0f172a"
                    cols[2].markdown(
                        f"<div style='text-align:right;font-size:1.08rem;font-weight:700;color:{cost_color};padding-top:8px;'>฿{r['unit_cost']:,.2f}</div>",
                        unsafe_allow_html=True,
                    )
                    cols[3].markdown(
                        f"<div style='text-align:right;font-size:1.0rem;color:#475569;padding-top:8px;'>฿{r['retail_price']:,.0f}</div>",
                        unsafe_allow_html=True,
                    )
                    cols[4].markdown(
                        f"<div style='text-align:right;font-size:1.0rem;color:#475569;padding-top:8px;'>฿{r['promo_price']:,.0f}</div>",
                        unsafe_allow_html=True,
                    )
                    cols[5].markdown(
                        f"<div style='text-align:right;font-size:1.0rem;color:#475569;padding-top:8px;'>฿{r['list_price']:,.0f}</div>",
                        unsafe_allow_html=True,
                    )
                    if cols[6].button("✏️ แก้ไข", key=f"edit_btn_{r['sku']}", width="stretch"):
                        edit_sku_dialog(r.to_dict())
                    if cols[7].button("🗑️", key=f"del_btn_{r['sku']}", width="stretch", help=f"ลบ {r['sku']}"):
                        db.delete_sku(str(r["sku"]))
                        _clear_export_caches()
                        st.toast(f"ลบ {r['sku']} เรียบร้อยแล้ว")
                        st.rerun()

            # แถบควบคุมหน้า (Pagination)
            pg_c1, pg_c2 = st.columns([1.5, 1.2])
            with pg_c1:
                st.caption(f"แสดงรายการที่ **{start_idx + 1} - {min(start_idx + page_size, total_items)}** จากทั้งหมด **{total_items:,}** รายการ")
            with pg_c2:
                p_prev, p_page, p_next = st.columns([1, 1.2, 1])
                if p_prev.button("◀ ก่อนหน้า", disabled=(cur_page <= 1), width="stretch", key="btn_sku_prev"):
                    st.session_state["sku_page_num"] = max(1, cur_page - 1)
                    st.rerun()
                p_page.markdown(f"<div style='text-align:center;padding-top:6px;font-size:0.95rem;color:#475569;'><b>{cur_page} / {total_pages}</b></div>", unsafe_allow_html=True)
                if p_next.button("ถัดไป ▶", disabled=(cur_page >= total_pages), width="stretch", key="btn_sku_next"):
                    st.session_state["sku_page_num"] = min(total_pages, cur_page + 1)
                    st.rerun()

# ==================== TAB 2: FACTORY OVERHEAD & COMMISSION ====================
with tab_fixed:
    with st.container(border=True):
        m_col1, m_col2, m_col3 = st.columns([1.2, 1.2, 1.4], gap="medium")
        selected_m = m_col1.selectbox("📅 เลือกงวดเดือน:", all_months, index=all_months.index(default_month))
        custom_m = m_col2.text_input("หรือพิมพ์งวดเดือนใหม่ (YYYY-MM):", value="", placeholder="เช่น 2026-08")
        active_m = custom_m.strip() if custom_m.strip() else selected_m

        cur_comm = db.get_comm_pct(active_m)
        with m_col3:
            new_comm = st.number_input(
                f"🤝 ค่าคอมคนขายงวด {active_m} (% กำไร)",
                min_value=0.0,
                max_value=100.0,
                value=cur_comm,
                step=1.0,
            )
            if new_comm != cur_comm:
                db.save_comm_pct(active_m, new_comm)
                st.toast(f"บันทึกค่าคอมคนขาย {new_comm:.0f}% สำหรับงวด {active_m} แล้ว")
                st.rerun()

        st.divider()
        h_left, h_add, h_clear = st.columns([2.2, 1.0, 0.9], gap="small")
        with h_left:
            render_section_header(f"รายการค่าใช้จ่ายโรงงานประจำงวด {active_m}", icon="🏭")
        if h_add.button("➕ เพิ่มค่าใช้จ่ายใหม่", type="primary", width="stretch"):
            add_expense_dialog(active_m)
        if h_clear.button("🗑️ ล้างเป็น 0 ทั้งงวด", type="secondary", width="stretch"):
            db.clear_fixed_costs(active_m)
            db.save_comm_pct(active_m, 0.0)
            st.toast(f"ล้างค่าใช้จ่ายงวด {active_m} เป็น 0 ทั้งหมดแล้ว")
            st.rerun()

        fc_df = db.get_fixed_costs(active_m)
        st.markdown(
            '<div style="background:#f8fafc;border-top:2px solid #e2e8f0;border-bottom:2px solid #e2e8f0;'
            'padding:12px 14px;margin-top:4px;font-size:1.05rem;font-weight:700;color:#1e293b;'
            'display:grid;grid-template-columns:3.2fr 1.4fr 1fr;gap:12px;align-items:center;">'
            "<div>รายการค่าใช้จ่าย (ค่าแรง / ค่าน้ำ / ค่าไฟ / อื่นๆ)</div>"
            '<div style="text-align:right;">จำนวนเงินต่อเดือน</div><div style="text-align:center;">จัดการ</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        if fc_df.empty:
            st.info(f"งวด {active_m} ยังไม่มีรายการค่าใช้จ่ายเพิ่มเติม (ระบบจะคำนวณเฉพาะราคาทุนจากชีต SKU)")
        else:
            for idx, r in fc_df.iterrows():
                ec1, ec2, ec3 = st.columns([3.2, 1.4, 1.0])
                ec1.markdown(f"<div style='font-size:1.08rem;font-weight:500;padding-top:8px;'>{html.escape(str(r['item']))}</div>", unsafe_allow_html=True)
                ec2.markdown(
                    f"<div style='text-align:right;font-size:1.15rem;font-weight:700;color:#0f172a;padding-top:8px;'>฿{r['amount']:,.2f}</div>",
                    unsafe_allow_html=True,
                )
                if ec3.button("✏️ แก้ไข / ลบ", key=f"exp_btn_{active_m}_{idx}", width="stretch"):
                    edit_expense_dialog(active_m, str(r["item"]), float(r["amount"]))

        total_fc = float(fc_df["amount"].sum()) if not fc_df.empty else 0.0
        st.markdown(
            f'<div style="background:#f1f5f9;border-radius:10px;padding:14px 18px;margin-top:14px;display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-size:1.1rem;font-weight:600;color:#334155;">รวมค่าใช้จ่ายโรงงานงวด {active_m}</span>'
            f'<b style="font-size:1.45rem;color:#0f172a;">{baht(total_fc)}</b>'
            f"</div>",
            unsafe_allow_html=True,
        )

# ==================== TAB 3: PRODUCT NAME TO SKU MAPPING ====================
with tab_mappings:
    with st.container(border=True):
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                        border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; color: white;">
                <div style="font-size: 1.05rem; font-weight: 800; color: #ffffff;">
                    🔗 จับคู่ชื่อสินค้ากับรหัส SKU (Product Name ↔ SKU Mappings)
                </div>
                <div style="font-size: 0.88rem; color: #c7d2fe; margin-top: 4px;">
                    ตารางนี้เก็บการเชื่อมโยงชื่อสินค้าที่ TikTok ส่งมาแบบไม่มี Seller SKU ให้ผูกกับรหัส SKU จริงในระบบอัตโนมัติ
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("➕ เพิ่มการจับคู่ชื่อสินค้ากับรหัส SKU ใหม่", expanded=False):
            with st.form("add_mapping_form"):
                map_pname = st.text_input("ชื่อสินค้าจาก TikTok (ตรงตามที่ปรากฏในไฟล์) *:", placeholder="เช่น โปรเปย์เดย์ โดสไฮโดร 100 ml. 2 ขวด...")
                master_sku_opts = [f"{s['sku']} | {str(s['name'])[:40]}" for s in skus.to_dict("records")]
                map_sku_sel = st.selectbox("เลือกรหัส SKU ที่ต้องการผูก:", options=master_sku_opts if master_sku_opts else ["-- ไม่มี SKU --"])
                map_custom_sku = st.text_input("หรือพิมพ์รหัส SKU ใหม่โดยตรง (ถ้าไม่อยู่ในรายการด้านบน):", placeholder="เช่น FZQCS009003")
                if st.form_submit_button("💾 บันทึกการจับคู่", type="primary", width="stretch"):
                    chosen_sku = map_custom_sku.strip() if map_custom_sku.strip() else (map_sku_sel.split(" | ")[0].strip() if " | " in map_sku_sel else "")
                    if not map_pname.strip():
                        st.error("กรุณาระบุชื่อสินค้า")
                    elif not chosen_sku or chosen_sku.startswith("--"):
                        st.error("กรุณาระบุรหัส SKU")
                    else:
                        db.upsert_sku_mapping(map_pname.strip(), chosen_sku)
                        st.toast(f"บันทึกการจับคู่ '{chosen_sku}' สำเร็จแล้ว")
                        st.rerun()

        mappings_df = db.list_sku_mappings()
        if mappings_df.empty:
            st.info("ℹ️ ยังไม่มีรายการจับคู่ชื่อสินค้ากับ SKU ในระบบ (เมื่อนำเข้าไฟล์และกดบันทึก SKU ที่ขาด รายการจะปรากฏที่นี่อัตโนมัติ)")
        else:
            st.caption(f"พบการจับคู่ทั้งหมด **{len(mappings_df):,} รายการ**")
            m_disp = mappings_df.rename(columns={
                "product_name": "ชื่อสินค้าใน TikTok",
                "sku": "รหัส SKU ที่ผูก",
                "unit_cost": "ราคาทุน (บาท)",
                "created_at": "วันที่บันทึก",
            })
            st.dataframe(
                m_disp[["ชื่อสินค้าใน TikTok", "รหัส SKU ที่ผูก", "ราคาทุน (บาท)", "วันที่บันทึก"]],
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("🗑️ ลบรายการจับคู่", expanded=False):
                del_target = st.selectbox("เลือกชื่อสินค้าที่ต้องการลบการจับคู่:", options=mappings_df["product_name"].tolist())
                if st.button("🗑️ ยืนยันลบการจับคู่นี้", type="secondary"):
                    db.delete_sku_mapping(del_target)
                    st.toast(f"ลบการจับคู่ '{del_target}' เรียบร้อยแล้ว")
                    st.rerun()

# ==================== TAB 4: EXCEL IMPORT / EXPORT ====================
with tab_bulk:
    col_in, col_out = st.columns(2, gap="medium")
    with col_in:
        with st.container(border=True):
            render_section_header("นำเข้าไฟล์ SKU (.xlsx)", icon="📥")
            st.caption("รองรับคอลัมน์ `รหัส, ชื่อ, ราคาทุน, ราคาปลีก, ราคาโปร, ราคาตั้งขาย` (และ `หมวดหมู่` ถ้ามี)")
            up = st.file_uploader("เลือกไฟล์ Excel ที่มีคอลัมน์ 'รหัส' และ 'ราคาทุน'", type=["xlsx"], key="sku_upload")
            if up is not None:
                raw_up = up.getvalue()
                wb_sku = load_workbook(BytesIO(raw_up), name=up.name)
                if not wb_sku.sku.empty:
                    df = wb_sku.sku.rename(
                        columns={
                            "รหัส": "sku",
                            "ชื่อ": "name",
                            "หมวดหมู่": "category",
                            "ราคาทุน": "unit_cost",
                            "ราคาปลีก": "retail_price",
                            "ราคาโปร": "promo_price",
                            "ราคาตั้งขาย": "list_price",
                        }
                    )
                else:
                    df = pd.read_excel(BytesIO(raw_up)).rename(
                        columns={
                            "รหัส": "sku",
                            "ชื่อ": "name",
                            "หมวดหมู่": "category",
                            "ราคาทุน": "unit_cost",
                            "ราคาปลีก": "retail_price",
                            "ราคาโปร": "promo_price",
                            "ราคาตั้งขาย": "list_price",
                        }
                    )
                if not {"sku", "unit_cost"} <= set(df.columns):
                    st.error("ไม่พบคอลัมน์ 'รหัส' และ 'ราคาทุน'")
                else:
                    if st.button(f"💾 นำเข้า {len(df)} รายการ", type="primary", width="stretch"):
                        st.success(f"นำเข้า {db.upsert_skus(df)} รายการสำเร็จ")
                        st.rerun()
    with col_out:
        with st.container(border=True):
            render_section_header("ส่งออกชีต SKU (.xlsx)", icon="📤")
            st.caption("ส่งออกคอลัมน์ `รหัส, ชื่อ, ราคาทุน, ราคาปลีก, ราคาโปร, ราคาตั้งขาย` ตรงตามรูปแบบไฟล์บริษัท")
            export_cols = ["sku", "name", "unit_cost", "retail_price", "promo_price", "list_price"]
            out = skus[export_cols].rename(
                columns={
                    "sku": "รหัส",
                    "name": "ชื่อ",
                    "unit_cost": "ราคาทุน",
                    "retail_price": "ราคาปลีก",
                    "promo_price": "ราคาโปร",
                    "list_price": "ราคาตั้งขาย",
                }
            )
            buf = BytesIO()
            out.to_excel(buf, index=False, sheet_name="SKU")
            st.download_button(
                "⬇️ ดาวน์โหลดไฟล์ SKU (.xlsx)",
                buf.getvalue(),
                file_name=f"SKU_Master_{date.today():%Y%m%d}.xlsx",
                type="primary",
                width="stretch",
            )
