from core.ui import init_page

init_page("รายงานและส่งออก", "📑")

from core.reloader import ensure_fresh

ensure_fresh()

import streamlit as st

from core import db
from core.export import (
    build_company_cost_master_excel,
    company_order_lines_view,
    company_settlement_view,
    format_thai_cost_filename,
    summary_table,
    to_excel,
    to_html_report,
)
from core.metrics import (
    by_category,
    by_sku,
    detect_anomalies,
    tiktok_report_table,
)
from core.pipeline import ALL_PERIODS_KEY
from core.ui import (
    build_saved_periods_comparison_df,
    render_page_header,
    render_period_selector,
    render_section_header,
    require_login,
    require_result,
    summarize_for_period,
)

require_login(admin_only=True)
res = require_result()
period = st.session_state.get("period", "")

render_page_header("รายงานตามโครงสร้าง TikTok Shop และดาวน์โหลดไฟล์", period=period)
period = render_period_selector(key="rep_period_sel")
s = summarize_for_period(res, period)

cat = by_category(res)
sku = by_sku(res)
anom = detect_anomalies(res)
tt_rep = tiktok_report_table(res)
settle_company = company_settlement_view(res.orders)
orders_company = company_order_lines_view(res.order_lines)
comp_df = build_saved_periods_comparison_df()
file_tag = "รวมทุกงวด" if period == ALL_PERIODS_KEY else period

with st.container(border=True):
    render_section_header("ดาวน์โหลดไฟล์ต้นทุนรวมและรายงานสรุป", icon="⬇️")
    e0, e1, e2 = st.columns(3, gap="medium")
    thai_cost_name = format_thai_cost_filename(period)

    export_sheets = {
        "รายงานตามโครงสร้าง TikTok": tt_rep,
        "เปรียบเทียบรายเดือน": comp_df,
        "สรุปราย SKU": sku,
        "ตามหมวดหมู่": cat,
        "รายละเอียดคำสั่งซื้อ": settle_company,
        "Order": orders_company,
        "คำสั่งซื้อที่ขายขาดทุน": anom["negative_profit"],
        "SKU ไม่มีราคาทุน": res.missing_skus,
    }
    if not res.withdrawals.empty:
        export_sheets["บันทึกการถอน"] = res.withdrawals

    sku_master_df = db.get_skus()
    excel_cache_key = f"{period}_{len(res.orders)}_{len(sku_master_df)}"
    has_cached_master = (
        st.session_state.get("_cached_master_excel_key") == excel_cache_key
        and st.session_state.get("_cached_master_excel_bytes") is not None
    )

    rep_cache_key = f"rep_{period}_{len(res.orders)}"
    if st.session_state.get("_cached_rep_key") != rep_cache_key:
        xlsx = to_excel(s, export_sheets)
        st.session_state["_cached_rep_xlsx"] = xlsx
        st.session_state["_cached_rep_key"] = rep_cache_key
    else:
        xlsx = st.session_state["_cached_rep_xlsx"]

    with e0:
        if has_cached_master:
            st.download_button(
                f"🎯 ดาวน์โหลดไฟล์ต้นทุนรวม ({thai_cost_name})",
                st.session_state["_cached_master_excel_bytes"],
                file_name=thai_cost_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
                key="rep_btn_master_cost",
            )
        else:
            if st.button(
                f"⚡ 1-Click สร้างไฟล์ต้นทุนรวม ({thai_cost_name})",
                type="primary",
                width="stretch",
                key="rep_btn_build_master",
                help="คลิกเพื่อประมวลผลไฟล์ต้นทุนรวม 7 ชีตฉบับเต็ม",
            ):
                with st.spinner("กำลังสร้างไฟล์ต้นทุนรวม 7 ชีต..."):
                    b = build_company_cost_master_excel(res, sku_master_df, period_label=period)
                    st.session_state["_cached_master_excel_bytes"] = b
                    st.session_state["_cached_master_excel_key"] = excel_cache_key
                    st.rerun()

    with e1:
        st.download_button(
            f"📗 ดาวน์โหลดรายงาน Excel ทุกชีต ({file_tag}.xlsx)",
            xlsx,
            file_name=f"รายงานต้นทุนกำไร_{file_tag}.xlsx",
            width="stretch",
            key="rep_btn_all_excel",
        )
    with e2:
        top = (
            sku.sort_values("ยอดขายหลังส่วนลด", ascending=False).head(10)[
                ["สถานะ", "SKU", "ชื่อสินค้า", "จำนวนขาย", "ยอดขายหลังส่วนลด", "กำไรขั้นต้น"]
            ]
            if not sku.empty
            else sku
        )
        html = to_html_report(s, file_tag, cat, top)
        st.download_button(
            f"📕 ดาวน์โหลดรายงาน 1 หน้า ({file_tag} PDF)",
            html.encode("utf-8"),
            file_name=f"รายงานผู้บริหาร_{file_tag}.html",
            mime="text/html",
            width="stretch",
            key="rep_btn_exec_html",
        )

tab_tt, tab_months, tab_pnl, tab_sku_loss, tab_wd = st.tabs(
    [
        "📋 โครงสร้างชีต 'รายงาน' (TikTok Shop)",
        "📆 เปรียบเทียบรายเดือน / สรุปทุกงวด",
        "🧾 งบกำไรขาดทุน & หมวดหมู่",
        "🚨 สินค้าขาดทุน / กำไรน้อยสุด",
        "🏦 บันทึกการถอน",
    ]
)

with tab_tt:
    with st.container(border=True):
        render_section_header("รายงานสรุปรายได้ ค่าธรรมเนียม และการปรับยอด ตามโครงสร้าง TikTok Shop", icon="📋")
        st.dataframe(tt_rep, width="stretch", hide_index=True, height=500)

with tab_months:
    with st.container(border=True):
        render_section_header("สรุปเปรียบเทียบผลประกอบการแยกตามแต่ละงวดเดือน", icon="📆")
        if comp_df.empty:
            st.caption("ยังไม่มีงวดที่บันทึกไว้ในระบบ")
        else:
            st.dataframe(comp_df, width="stretch", hide_index=True)

with tab_pnl:
    c_pnl, c_cat = st.columns([1.05, 1.25], gap="medium")
    with c_pnl:
        with st.container(border=True):
            render_section_header("สรุปกำไร / ขาดทุน ประจำงวด", icon="🧾")
            st.dataframe(summary_table(s), width="stretch", hide_index=True, height=440)

    with c_cat:
        with st.container(border=True):
            render_section_header("สรุปตามหมวดหมู่สินค้า", icon="📂")
            st.dataframe(cat, width="stretch", hide_index=True, height=440)

with tab_sku_loss:
    with st.container(border=True):
        render_section_header("รายการสินค้าที่ขาดทุน / กำไรน้อยที่สุด 10 อันดับแรก (เทียบราคาทุน SKU)", icon="🚨")
        if sku.empty:
            st.caption("ไม่มีข้อมูล")
        else:
            st.dataframe(
                sku.head(10)[
                    ["สถานะ", "SKU", "ชื่อสินค้า", "จำนวนขาย", "ราคาทุน/หน่วย", "ยอดการชำระเงินทั้งหมด", "มูลค่าต้นทุน", "กำไรขั้นต้น"]
                ].rename(columns={"กำไรขั้นต้น": "กำไร / ขาดทุน"}),
                width="stretch",
                hide_index=True,
            )

with tab_wd:
    with st.container(border=True):
        render_section_header("ชีต 'บันทึกการถอน' (รวมรายการ GMV Pay Deduction)", icon="🏦")
        if res.withdrawals.empty:
            st.info("ไม่พบข้อมูลในชีต 'บันทึกการถอน' ของงวดนี้")
        else:
            st.dataframe(res.withdrawals, width="stretch", hide_index=True, height=360)
