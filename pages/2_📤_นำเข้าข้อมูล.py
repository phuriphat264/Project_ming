from core.ui import init_page

init_page("นำเข้า & คำนวณต้นทุนรวม", "📤")

from core.reloader import ensure_fresh

ensure_fresh()

from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import streamlit as st

from core import db, order_repo
from core.export import (
    build_company_cost_master_excel,
    company_order_lines_view,
    company_settlement_view,
    format_thai_cost_filename,
    summary_table,
    to_excel,
    to_html_report,
)
from core.loader import (
    FEE_DESCRIPTIONS,
    LoadedWorkbook,
    ORDER_KEY,
    SETTLEMENT_KEY,
    get_data_dir,
    load_workbook,
    scan_data_directory,
)
from core.metrics import (
    by_category,
    by_sku,
    detect_anomalies,
    summarize,
    tiktok_report_table,
)
from core.pipeline import (
    ALL_PERIODS_KEY,
    combine,
    detect_period_label,
    extract_order_skus,
    recalculate_with_skus,
    run_pipeline,
)
from core.ui import (
    baht,
    get_current_shop,
    is_admin,
    load_period_result,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
    summarize_for_period,
)

user = require_login()

render_page_header(
    "ระบบจัดการและคำนวณต้นทุนรวม (TikTok Shop)",
    subtitle="นำเข้า 2 ไฟล์ (คำสั่งซื้อ + Income) หรืออ่านจากโฟลเดอร์ data เพื่อสร้างไฟล์ต้นทุนรวม ต้นทุน(ปี-เดือน).xlsx อัตโนมัติ",
    period=st.session_state.get("period"),
)


def _save_period_snapshot(period_name: str, res_obj, shop_code: str | None = None) -> None:
    fixed = db.total_fixed_cost(period_name)
    comm_pct = db.get_comm_pct(period_name)
    s_obj = summarize(res_obj, fixed_costs=fixed, comm_pct=comm_pct)
    db.save_snapshot(
        month=period_name,
        summary_dict=s_obj.as_dict(),
        orders_df=res_obj.orders,
        lines_df=res_obj.order_lines,
        ads_df=res_obj.ads,
        source=res_obj.source,
        warnings=res_obj.warnings,
        fee_details=res_obj.fee_details,
        withdrawals_df=res_obj.withdrawals,
        raw_settlement_df=getattr(res_obj, "raw_settlement", None),
        raw_orders_df=getattr(res_obj, "raw_orders", None),
        shop_code=shop_code,
    )


def _process_income_with_orders(
    income_name: str,
    income_bytes: bytes,
    order_items: list[tuple[str, bytes]],
    use_repo: bool,
    shop: dict | str | None = None,
) -> None:
    """อ่าน Income + ไฟล์ Order (1 ไฟล์หรือมากกว่า) → เติมออเดอร์เดือนก่อนจากคลัง → คำนวณ → บันทึก Order ใหม่ลงคลัง"""
    b_inc = load_workbook(BytesIO(income_bytes), name=income_name)
    b_ords = [load_workbook(BytesIO(ob), name=on) for on, ob in order_items]
    if b_inc.settlement.empty:
        raise ValueError(f"ไม่พบชีต 'รายละเอียดคำสั่งซื้อ' ในไฟล์ Income: {income_name}")
    for b in b_ords:
        if b.orders.empty:
            raise ValueError(f"ไม่พบชีตคำสั่งซื้อ (Order ID / Seller SKU / Quantity) ในไฟล์: {b.name}")

    combined = combine([b_inc, *b_ords])
    new_raw_orders = combined.raw_orders.copy()  # เฉพาะ Order ที่อัปโหลดรอบนี้ (ใช้บันทึกลงคลัง)

    s_code = shop.get("code") if isinstance(shop, dict) else (shop or "matang")
    pulled = 0
    if use_repo:
        combined, pulled = order_repo.attach_repo_orders(combined, shop_code=s_code)

    if not combined.orders.empty:
        db.add_missing_skus(extract_order_skus(combined.orders))

    sku_master = db.get_skus()
    result = run_pipeline(combined, sku_master)
    all_names = [income_name] + [on for on, _ in order_items]
    period = detect_period_label(result, all_names, shop=shop)

    for fname, fbytes in [(income_name, income_bytes), *order_items]:
        db.save_uploaded_excel(original_name=fname, raw_bytes=fbytes, period=period, uploaded_by=user["username"])

    repo_stat = order_repo.save_to_repo(new_raw_orders, shop_code=s_code)

    if is_admin():
        _save_period_snapshot(period, result, shop_code=s_code)
        db.set_app_state("active_period", period)

    # แคชเตรียมไฟล์ Master Excel ล่วงหน้าระหว่างที่มี spinner นำเข้า
    try:
        master_bytes = build_company_cost_master_excel(result, sku_master, period_label=period)
        st.session_state["_cached_master_excel_bytes"] = master_bytes
        st.session_state["_cached_master_excel_key"] = f"{period}_{len(result.orders)}_{len(sku_master)}"
    except Exception:
        pass

    st.session_state.update(result=result, period=period, raw=combined, notes=combined.notes)

    warn_msgs = []
    no_cost = next((w for w in result.warnings if "ไม่พบในชีต Order" in w), "")
    if no_cost:
        warn_msgs.append(no_cost)
    if not result.missing_skus.empty:
        warn_msgs.append(f"⚠️ ตรวจพบ {len(result.missing_skus):,} สินค้าที่ยังไม่มีราคาทุนในระบบ (ระบบเปิดตารางให้กรอกราคาทุนทันทีที่ด้านล่าง เพื่อคำนวณกำไรให้ครบ 100%)")
    combined_warn = " · ".join(warn_msgs)

    msg = (
        f"✅ คำนวณสำเร็จ งวด **{period}** → ไฟล์ต้นทุนรวม **`{format_thai_cost_filename(period)}`**  \n"
        f"• ไฟล์ Order ที่ใส่รอบนี้: **{len(order_items)} ไฟล์** · รายละเอียดคำสั่งซื้อ **{len(result.orders):,} รายการ** · "
        f"รายการสินค้า **{len(result.order_lines):,} แถว**  \n"
        f"• ดึงออเดอร์เดือนก่อนจากคลังสะสม: **{pulled:,} ออเดอร์**  \n"
        f"• บันทึกลงคลังคำสั่งซื้อสะสม: ใหม่ **{repo_stat['added']:,}** · อัปเดต **{repo_stat['replaced']:,}** · "
        f"รวมในคลัง **{repo_stat['total']:,} ออเดอร์**"
    )
    st.session_state["import_flash"] = (msg, combined_warn)
    st.rerun()


def _render_missing_skus_editor(res_obj, sku_df, period_name: str, key_prefix: str = "top") -> None:
    """ตารางและแบบฟอร์มกำหนดรหัส SKU และราคาทุนให้สินค้าที่ไม่มี SKU พร้อมคำนวณกำไรใหม่ทันที"""
    if res_obj.missing_skus.empty:
        st.success("✅ สินค้าทุกรหัสในงวดนี้มีรหัส SKU และราคาทุนครบ 100% แล้ว")
        return

    edit_df = res_obj.missing_skus.copy()
    q_col = "qty" if "qty" in edit_df.columns else edit_df.columns[0]
    o_col = "orders_count" if "orders_count" in edit_df.columns else None

    sku_to_list = dict(zip(sku_df["sku"].astype(str).str.strip(), sku_df["list_price"]))
    sku_to_cost = dict(zip(sku_df["sku"].astype(str).str.strip(), sku_df["unit_cost"]))
    sku_to_name = dict(zip(sku_df["sku"].astype(str).str.strip(), sku_df["name"]))

    # =========================================================================
    # ส่วนที่ 1: แบบฟอร์มกำหนดรหัส SKU (ขอช่องใส่ SKU ให้ตัวที่ไม่มี SKU)
    # =========================================================================
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                    border-radius: 14px; padding: 16px 20px; margin-bottom: 16px; color: white;
                    box-shadow: 0 4px 16px rgba(49, 46, 129, 0.25);">
            <div style="font-size: 1.12rem; font-weight: 800; color: #ffffff; display: flex; align-items: center; gap: 8px;">
                🏷️ กำหนดรหัส SKU และราคาทุนให้สินค้า (Manual SKU & Cost Assignment)
            </div>
            <div style="font-size: 0.88rem; color: #c7d2fe; margin-top: 4px;">
                สำหรับสินค้าที่ไฟล์ TikTok ไม่มี Seller SKU มา คุณสามารถ <b>พิมพ์กำหนดรหัส SKU เอง</b> หรือ <b>เลือกจับคู่กับ SKU ที่มีอยู่แล้ว</b> ระบบจะบันทึกจำไว้ตลอดไป
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    items_list = edit_df.to_dict("records")
    def _item_fmt(idx: int) -> str:
        row = items_list[idx]
        sku_lbl = f"[{row['sku']}] " if row['sku'] != "(ไม่ระบุ SKU)" else "[⚠️ ไม่มี SKU] "
        qty_v = int(row[q_col]) if pd.notna(row[q_col]) else 0
        ord_v = int(row[o_col]) if o_col and pd.notna(row[o_col]) else 1
        return f"{sku_lbl}{str(row['name'])[:55]}... ({qty_v:,} ชิ้น / {ord_v:,} ออเดอร์)"

    sel_idx = st.selectbox(
        "📦 1. เลือกสินค้าที่ต้องการกำหนดรหัส SKU / ใส่ราคาทุน:",
        options=list(range(len(items_list))),
        format_func=_item_fmt,
        key=f"{key_prefix}_sel_missing_item_idx",
    )
    cur_item = items_list[sel_idx]
    orig_name = str(cur_item.get("name", "")).strip()
    orig_sku = str(cur_item.get("sku", "")).strip()
    is_blank_sku = orig_sku in ("(ไม่ระบุ SKU)", "", "None", "nan")

    with st.container(border=True):
        st.markdown(f"**สินค้าที่เลือก:** `{orig_name}`")
        f_col1, f_col2 = st.columns([1.5, 1.2], gap="large")

        # รายการ SKU Master เดิมที่มีอยู่
        master_skus = sku_df[sku_df["sku"].astype(str).str.strip() != ""].to_dict("records")
        master_opts = ["-- หรือพิมพ์รหัส SKU ใหม่ในช่องด้านล่าง --"] + [
            f"{s['sku']} | {str(s['name'])[:40]} (ทุน ฿{s['unit_cost']:.2f})" for s in master_skus
        ]

        with f_col1:
            sel_master = st.selectbox(
                "🔗 เลือกจับคู่กับ SKU ที่มีอยู่ในระบบแล้ว (ถ้ามี):",
                options=master_opts,
                index=0,
                key=f"{key_prefix}_sel_master_match",
                help="หากสินค้านี้ตรงกับ SKU ใดในคลัง เลือกตรงนี้เพื่อดึงรหัสและราคาทุนมาใช้ทันที",
            )
            prefill_sku = ""
            prefill_cost = 0.0
            prefill_list = 0.0
            if sel_master != master_opts[0]:
                matched_sku_code = sel_master.split(" | ")[0].strip()
                prefill_sku = matched_sku_code
                prefill_cost = float(sku_to_cost.get(matched_sku_code, 0.0))
                prefill_list = float(sku_to_list.get(matched_sku_code, 0.0))
            elif not is_blank_sku:
                prefill_sku = orig_sku

            assigned_sku = st.text_input(
                "🏷️ ช่องพิมพ์รหัส SKU ที่ต้องการกำหนดให้สินค้านี้ *:",
                value=prefill_sku,
                placeholder="เช่น FZQCS009003 หรือ รหัสสินค้าที่ต้องการ",
                key=f"{key_prefix}_input_assigned_sku",
                help="พิมพ์รหัส SKU ของสินค้าชิ้นนี้ (ระบบจะผูกชื่อสินค้านี้เข้ากับรหัส SKU นี้ตลอดไป)",
            )
            assigned_name = st.text_input(
                "📝 ชื่อสินค้า (แก้ไขได้หากต้องการ):",
                value=orig_name,
                key=f"{key_prefix}_input_assigned_name",
            )

        with f_col2:
            assigned_cost = st.number_input(
                "💵 ราคาทุนต่อหน่วย (บาท) *:",
                min_value=0.0,
                step=1.0,
                value=prefill_cost if prefill_cost > 0 else 0.0,
                format="฿%.2f",
                key=f"{key_prefix}_input_assigned_cost",
                help="ต้นทุนต่อ 1 ชิ้นของสินค้านี้",
            )
            assigned_list = st.number_input(
                "🏷️ ราคาตั้งขาย (บาท):",
                min_value=0.0,
                step=1.0,
                value=prefill_list if prefill_list > 0 else float(sku_to_list.get(orig_sku, 0.0)),
                format="฿%.2f",
                key=f"{key_prefix}_input_assigned_list",
            )
            assigned_cat = st.text_input(
                "📁 หมวดหมู่สินค้า:",
                value=str(cur_item.get("category", "ทั่วไป")),
                key=f"{key_prefix}_input_assigned_cat",
            )

            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            if st.button("💾 บันทึกรหัส SKU และคำนวณกำไรใหม่ทันที ⚡", type="primary", width="stretch", key=f"{key_prefix}_btn_assign_sku"):
                clean_sku_val = assigned_sku.strip()
                if not clean_sku_val or clean_sku_val in ("(ไม่ระบุ SKU)", "nan", "None"):
                    st.error("⚠️ กรุณาระบุรหัส SKU ในช่อง '🏷️ ช่องพิมพ์รหัส SKU ที่ต้องการกำหนดให้สินค้านี้'")
                elif assigned_cost <= 0:
                    st.warning("⚠️ กรุณาระบุราคาทุนต่อหน่วยที่มากกว่า 0 บาท")
                else:
                    # 1. บันทึกการจับคู่ชื่อสินค้า -> SKU ลงฐานข้อมูล
                    db.upsert_sku_mapping(orig_name, clean_sku_val)
                    if assigned_name != orig_name:
                        db.upsert_sku_mapping(assigned_name, clean_sku_val)

                    # 2. บันทึก SKU เข้าสู่ Master
                    db.upsert_sku(
                        sku=clean_sku_val,
                        name=assigned_name,
                        category=assigned_cat.strip() or "ทั่วไป",
                        unit_cost=assigned_cost,
                        list_price=assigned_list,
                    )

                    # 3. อัปเดต Seller SKU ลงใน Order Lines ของชุดข้อมูลปัจจุบันทันที
                    if not res_obj.order_lines.empty and "Product Name" in res_obj.order_lines.columns:
                        mask_pn = res_obj.order_lines["Product Name"].fillna("").astype(str).str.strip() == orig_name
                        res_obj.order_lines.loc[mask_pn, "Seller SKU"] = clean_sku_val

                    # 4. คำนวณใหม่
                    new_sku_df = db.get_skus()
                    updated_res = recalculate_with_skus(res_obj, new_sku_df)
                    st.session_state["result"] = updated_res
                    st.session_state.pop("_cached_master_excel_bytes", None)
                    st.session_state.pop("_cached_master_excel_key", None)

                    s_code = getattr(updated_res, "source", None) or "matang"
                    if is_admin():
                        _save_period_snapshot(period_name, updated_res, shop_code=s_code)

                    st.toast(f"✅ บันทึกรหัส SKU '{clean_sku_val}' และคำนวณกำไรใหม่เรียบร้อยแล้ว!", icon="🎉")
                    st.rerun()

    # =========================================================================
    # ส่วนที่ 2: ตาราง Data Editor สำหรับกรอกแบบเร็วหลายรายการ
    # =========================================================================
    with st.expander("📋 หรือเปิดตารางกรอกราคาทุนแบบตารางด่วน (Bulk Data Editor)", expanded=False):
        edit_display = pd.DataFrame({
            "รหัส SKU (ระบุรหัสได้ที่นี่ ⭐)": edit_df["sku"].astype(str).replace({"(ไม่ระบุ SKU)": ""}),
            "ชื่อสินค้า": edit_df["name"].fillna("").astype(str),
            "หมวดหมู่": edit_df["category"].fillna("ทั่วไป").astype(str),
            "จำนวนที่ขาย (ชิ้น)": pd.to_numeric(edit_df[q_col], errors="coerce").fillna(0).astype(int),
            "จำนวนออเดอร์": pd.to_numeric(edit_df[o_col], errors="coerce").fillna(1).astype(int) if o_col else 1,
            "ราคาทุนต่อหน่วย (บาท)": 0.0,
            "ราคาตั้งขาย (บาท)": edit_df["sku"].astype(str).str.strip().map(sku_to_list).fillna(0.0).astype(float),
        })

        st.caption("💡 ดับเบิลคลิกที่ช่อง 'รหัส SKU' เพื่อพิมพ์รหัส และดับเบิลคลิกที่ช่อง 'ราคาทุนต่อหน่วย' เพื่อพิมพ์ต้นทุน")
        edited_data = st.data_editor(
            edit_display,
            column_config={
                "รหัส SKU (ระบุรหัสได้ที่นี่ ⭐)": st.column_config.TextColumn(
                    "รหัส SKU (ระบุรหัสได้ที่นี่ ⭐)",
                    help="พิมพ์รหัสสินค้า SKU ได้โดยตรง เช่น FZQCS009003",
                ),
                "ชื่อสินค้า": st.column_config.TextColumn("ชื่อสินค้า", disabled=True),
                "หมวดหมู่": st.column_config.TextColumn("หมวดหมู่", disabled=True),
                "จำนวนที่ขาย (ชิ้น)": st.column_config.NumberColumn("จำนวนที่ขาย (ชิ้น)", disabled=True, format="%d"),
                "จำนวนออเดอร์": st.column_config.NumberColumn("จำนวนออเดอร์", disabled=True, format="%d"),
                "ราคาทุนต่อหน่วย (บาท)": st.column_config.NumberColumn(
                    "ราคาทุนต่อหน่วย (บาท) ⭐",
                    min_value=0.0,
                    step=1.0,
                    format="฿%.2f",
                    required=True,
                ),
                "ราคาตั้งขาย (บาท)": st.column_config.NumberColumn(
                    "ราคาตั้งขาย (บาท)",
                    min_value=0.0,
                    step=1.0,
                    format="฿%.2f",
                ),
            },
            hide_index=True,
            width="stretch",
            key=f"{key_prefix}_missing_sku_editor",
        )

        c_save1, c_save2 = st.columns([2.5, 1.5], gap="medium")
        with c_save1:
            if st.button("💾 บันทึกราคาทุนจากตาราง และคำนวณใหม่ทันที ⚡", type="primary", width="stretch", key=f"{key_prefix}_btn_save_missing_skus"):
                filled_rows = edited_data[edited_data["ราคาทุนต่อหน่วย (บาท)"] > 0]
                if filled_rows.empty:
                    st.warning("⚠️ กรุณากรอกราคาทุนในช่อง 'ราคาทุนต่อหน่วย (บาท)' อย่างน้อย 1 สินค้าก่อนกดบันทึก")
                else:
                    saved_count = 0
                    for _, r in filled_rows.iterrows():
                        s_code = str(r["รหัส SKU (ระบุรหัสได้ที่นี่ ⭐)"]).strip()
                        p_name = str(r["ชื่อสินค้า"]).strip()
                        if s_code and s_code not in ("(ไม่ระบุ SKU)", "nan", "None"):
                            db.upsert_sku_mapping(p_name, s_code)
                            if not res_obj.order_lines.empty and "Product Name" in res_obj.order_lines.columns:
                                mask_pn = res_obj.order_lines["Product Name"].fillna("").astype(str).str.strip() == p_name
                                res_obj.order_lines.loc[mask_pn, "Seller SKU"] = s_code
                        else:
                            s_code = p_name

                        db.upsert_sku(
                            sku=s_code,
                            name=p_name,
                            category=str(r["หมวดหมู่"]).strip(),
                            unit_cost=float(r["ราคาทุนต่อหน่วย (บาท)"]),
                            list_price=float(r["ราคาตั้งขาย (บาท)"]),
                        )
                        saved_count += 1

                    new_sku_df = db.get_skus()
                    updated_res = recalculate_with_skus(res_obj, new_sku_df)
                    st.session_state["result"] = updated_res
                    st.session_state.pop("_cached_master_excel_bytes", None)
                    st.session_state.pop("_cached_master_excel_key", None)

                    s_code = getattr(updated_res, "source", None) or "matang"
                    if is_admin():
                        _save_period_snapshot(period_name, updated_res, shop_code=s_code)

                    st.toast(f"✅ บันทึกข้อมูลสำเร็จ {saved_count} สินค้า และคำนวณกำไรใหม่แล้ว!", icon="🎉")
                    st.rerun()

        with c_save2:
            if st.button("🔄 รีเซ็ตตาราง", width="stretch", key=f"{key_prefix}_btn_refresh_sku"):
                st.rerun()


# ==============================================================================
# ส่วนที่ 1: การกรอกไฟล์และนำเข้าข้อมูล (Data Input Section)
# ==============================================================================
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%); padding: 20px 26px; border-radius: 16px; margin-bottom: 22px; box-shadow: 0 4px 20px -2px rgba(79, 70, 229, 0.3); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div>
            <div style="display: inline-block; background: rgba(255, 255, 255, 0.2); color: #ffffff; font-size: 0.78rem; font-weight: 800; padding: 3px 10px; border-radius: 6px; letter-spacing: 0.05em; margin-bottom: 6px;">STEP 01</div>
            <h3 style="color: white; margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em;">📥 การกรอกไฟล์และนำเข้าข้อมูล (Data Input)</h3>
            <p style="color: #e0e7ff; margin: 4px 0 0 0; font-size: 0.95rem;">
                เลือกวิธีนำเข้า: 1) อัปโหลด 2 ไฟล์ (ไฟล์คำสั่งซื้อ + ไฟล์รายได้) หรือ 2) โหลดด่วนจากโฟลเดอร์ <code>data/</code>
            </p>
        </div>
        <div style="font-size: 2.2rem; opacity: 0.9;">⚡</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# สแกนหาไฟล์ในโฟลเดอร์ data/
data_scan = scan_data_directory()
data_orders_files = data_scan.get("orders", [])
data_income_files = data_scan.get("income", [])

# แสดงผลลัพธ์จากการนำเข้ารอบล่าสุด (เก็บไว้ข้าม st.rerun)
_flash = st.session_state.pop("import_flash", None)
if _flash:
    st.success(_flash[0])
    if _flash[1]:
        st.warning(f"⚠️ {_flash[1]}")

# ------------------------------------------------------------------------------
# สถานะคลังคำสั่งซื้อสะสม + คำแนะนำว่ารอบนี้ต้องใส่ไฟล์ Order กี่ไฟล์
# ------------------------------------------------------------------------------
repo_info = order_repo.repo_summary()
repo_empty = repo_info["orders"] == 0

with st.container(border=True):
    rc1, rc2 = st.columns([2.2, 1.0], gap="medium")
    with rc1:
        st.markdown("#### 🗄️ คลังคำสั่งซื้อสะสม (Order Repository)")
        if repo_empty:
            st.info(
                "🟢 **เริ่มระบบครั้งแรก:** คลังยังว่าง — กรุณาใส่ **Income 1 ไฟล์ + ไฟล์คำสั่งซื้อ 2 ไฟล์** "
                "(เดือนก่อน + เดือนนี้ เช่น Order8 + Order9) เพราะ Income หนึ่งรอบมีออเดอร์ที่สั่งปลายเดือนก่อนปนอยู่ด้วย"
            )
        else:
            latest_m = repo_info["months"]["เดือนที่สั่งซื้อ"].iloc[0]
            st.success(
                f"🔵 **รอบถัดไป:** ในคลังมี **{repo_info['orders']:,} ออเดอร์** (ล่าสุดเดือน **{latest_m}**) — "
                "ใส่แค่ **Income + ไฟล์คำสั่งซื้อเดือนล่าสุด 1 ไฟล์** ได้เลย ระบบจะดึงออเดอร์เดือนก่อนจากคลังมาคิดต้นทุนให้อัตโนมัติ"
            )
        use_repo = st.checkbox(
            "ดึงคำสั่งซื้อเดือนก่อนจากคลังสะสมอัตโนมัติ (แนะนำ)",
            value=True,
            disabled=repo_empty,
            key="use_order_repo",
        )
    with rc2:
        if not repo_empty:
            st.dataframe(repo_info["months"], hide_index=True, width="stretch", height=150)
            if is_admin():
                with st.popover("🗑️ จัดการ / เลือกลบคลังคำสั่งซื้อ", width="stretch"):
                    month_list = repo_info["months"]["เดือนที่สั่งซื้อ"].tolist()
                    st.markdown("##### 📌 1. เลือกลบเฉพาะเดือน (ลบทีละงวด)")
                    st.caption("เลือกเดือนที่ต้องการลบออกจากคลัง (เดือนอื่นจะยังอยู่ครบ)")
                    del_m = st.selectbox("เลือกเดือนที่ต้องการลบ:", month_list, key="sel_del_repo_m")
                    if st.button(f"🗑️ ยืนยันลบเดือน {del_m}", type="primary", key="btn_del_single_repo_m", width="stretch"):
                        cnt = order_repo.delete_month_from_repo(del_m)
                        for k in ("_cached_master_excel_bytes", "_cached_master_excel_key", "_cached_rep_key", "_cached_rep_master_xlsx", "_cached_rep_xlsx", "sel_del_repo_m"):
                            st.session_state.pop(k, None)
                        st.toast(f"ลบออเดอร์เดือน {del_m} ออกจากคลังเรียบร้อยแล้ว ({cnt:,} ออเดอร์)", icon="🗑️")
                        st.rerun()

                    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                    st.divider()
                    st.markdown("##### ⚠️ 2. ล้างคลังทั้งหมด (Reset ทั้งระบบ)")
                    st.caption("ลบออเดอร์ทุกเดือนทิ้งทั้งหมด (รอบถัดไปต้องใส่ไฟล์ Order 2 ไฟล์ใหม่)")
                    if st.button("ยืนยันล้างคลังทั้งหมด", type="secondary", key="btn_clear_order_repo", width="stretch"):
                        order_repo.clear_repo()
                        for k in ("_cached_master_excel_bytes", "_cached_master_excel_key", "_cached_rep_key", "_cached_rep_master_xlsx", "_cached_rep_xlsx", "sel_del_repo_m"):
                            st.session_state.pop(k, None)
                        st.toast("ล้างคลังคำสั่งซื้อสะสมทั้งหมดแล้ว", icon="🗑️")
                        st.rerun()

recommended_order_files = 2 if repo_empty else 1


def _check_order_count(n_files: int) -> None:
    if n_files == 1 and repo_empty:
        st.warning(
            "⚠️ คลังคำสั่งซื้อยังว่าง และเลือกไฟล์ Order ไว้แค่ 1 ไฟล์ — ออเดอร์ที่สั่งในเดือนก่อน "
            "(แต่เงินเข้ารอบนี้) จะหาต้นทุนไม่เจอ แนะนำให้เพิ่มไฟล์ Order เดือนก่อนหน้าอีก 1 ไฟล์"
        )


# -----------------------------------------------------------------------------
# เลือกช่องทาง / ร้านค้า TikTok Shop (Multi-Channel Support)
# -----------------------------------------------------------------------------
shops_list = db.list_shops(active_only=True)
shop_codes = [s["code"] for s in shops_list]
shop_map = {s["code"]: s for s in shops_list}

active_shop = get_current_shop()
if "global_upload_shop_select" not in st.session_state or st.session_state["global_upload_shop_select"] not in shop_codes:
    st.session_state["global_upload_shop_select"] = active_shop["code"]

col_s1, col_s2 = st.columns([3, 1.2], vertical_alignment="bottom")
with col_s1:
    def _shop_lbl(c: str) -> str:
        item = shop_map.get(c, {})
        handle = f" ({item.get('tiktok_handle')})" if item.get("tiktok_handle") else ""
        star = " ★ (ช่องทางหลัก)" if item.get("is_default") else ""
        return f"🏬 {item.get('name', c)}{handle}{star}"

    def _on_upload_shop_change():
        sel_c = st.session_state.get("global_upload_shop_select")
        if sel_c:
            set_current_shop(sel_c)

    cur_selected_shop_code = st.selectbox(
        "🏬 เลือกร้านค้า / ช่องทาง TikTok Shop ของชุดข้อมูลนี้:",
        options=shop_codes,
        format_func=_shop_lbl,
        key="global_upload_shop_select",
        on_change=_on_upload_shop_change,
        help="เลือกร้านค้าเพื่อแยกเก็บผลการวิเคราะห์และส่งออกไฟล์ต้นทุนตามชื่อร้าน",
    )
    active_shop_info = shop_map.get(cur_selected_shop_code, shops_list[0])

with col_s2:
    if st.button("➕ เพิ่ม/จัดการช่องทาง", width="stretch", help="เพิ่มหรือแก้ไขรายชื่อช่องทาง TikTok"):
        st.session_state["show_shop_manager_inline"] = not st.session_state.get("show_shop_manager_inline", False)

if st.session_state.get("show_shop_manager_inline"):
    with st.expander("🏬 จัดการรายชื่อร้านค้า / ช่องทาง TikTok Shop (เพิ่ม, แก้ไข, ลบ)", expanded=True):
        m_c1, m_c2 = st.columns([1.3, 1.2], gap="medium")
        with m_c1:
            st.markdown("###### รายชื่อช่องทางทั้งหมดในระบบ:")
            all_db_shops = db.list_shops(active_only=False)
            df_sh = pd.DataFrame(all_db_shops)
            if not df_sh.empty:
                df_sh["สถานะ"] = df_sh["is_active"].apply(lambda a: "🟢 เปิด" if a else "⚪ ปิด")
                df_sh["ประเภท"] = df_sh["is_default"].apply(lambda d: "★ ร้านหลัก" if d else "ร้านย่อย")
                st.dataframe(
                    df_sh[["code", "name", "tiktok_handle", "ประเภท", "สถานะ"]].rename(
                        columns={"code": "รหัสร้าน", "name": "ชื่อร้าน/ช่องทาง", "tiktok_handle": "TikTok Handle"}
                    ),
                    hide_index=True,
                    width="stretch",
                )

        with m_c2:
            tab_sm_add, tab_sm_edit, tab_sm_del = st.tabs(["➕ เพิ่มร้านใหม่", "✏️ แก้ไขร้าน", "🗑️ ลบร้าน"])
            with tab_sm_add:
                with st.form("form_add_shop_inline", clear_on_submit=True):
                    new_s_code = st.text_input("รหัสร้าน (ภาษาอังกฤษ เช่น live1) *", placeholder="เช่น live1").strip().lower()
                    new_s_name = st.text_input("ชื่อร้าน/ช่องทาง *", placeholder="เช่น มาตัง ไลฟ์สด 1").strip()
                    new_s_handle = st.text_input("TikTok Handle", placeholder="@matang_live").strip()
                    new_s_def = st.checkbox("ตั้งเป็นร้านหลัก", value=False)
                    if st.form_submit_button("➕ บันทึกร้านค้าใหม่", type="primary", width="stretch"):
                        if new_s_code and new_s_name:
                            db.upsert_shop(new_s_code, new_s_name, new_s_handle, is_default=new_s_def)
                            st.toast(f"✅ เพิ่มช่องทาง {new_s_name} เรียบร้อยแล้ว", icon="🏬")
                            st.rerun()
                        else:
                            st.error("กรุณากรอกรหัสร้านและชื่อร้าน")

            with tab_sm_edit:
                all_codes = [s["code"] for s in all_db_shops]
                ed_code = st.selectbox("เลือกร้านที่ต้องการแก้ไข:", options=all_codes, key="inline_sel_edit_shop")
                cur_s_data = next((s for s in all_db_shops if s["code"] == ed_code), all_db_shops[0])
                with st.form("form_edit_shop_inline"):
                    st.text_input("รหัสร้าน (Code)", value=cur_s_data["code"], disabled=True)
                    ed_name = st.text_input("ชื่อร้าน / ช่องทาง *", value=cur_s_data["name"]).strip()
                    ed_handle = st.text_input("TikTok Handle", value=cur_s_data["tiktok_handle"]).strip()
                    ed_def = st.checkbox("ตั้งเป็นร้านหลัก", value=bool(cur_s_data["is_default"]))
                    ed_act = st.checkbox("เปิดใช้งาน", value=bool(cur_s_data["is_active"]))
                    if st.form_submit_button("💾 บันทึกการแก้ไข", type="primary", width="stretch"):
                        if ed_name:
                            db.upsert_shop(cur_s_data["code"], ed_name, ed_handle, is_default=ed_def, is_active=ed_act)
                            st.toast(f"✅ อัปเดตข้อมูลร้าน {ed_name} สำเร็จแล้ว", icon="🎉")
                            st.rerun()
                        else:
                            st.error("กรุณากรอกชื่อร้าน")

            with tab_sm_del:
                del_list = [s["code"] for s in all_db_shops if not s.get("is_default") and len(all_db_shops) > 1]
                if del_list:
                    d_code = st.selectbox("เลือกร้านที่ต้องการลบ:", options=del_list, key="inline_sel_del_shop")
                    d_shop_info = next((s for s in all_db_shops if s["code"] == d_code), None)
                    d_name = d_shop_info["name"] if d_shop_info else d_code
                    st.warning(f"⚠️ ยืนยันการลบช่องทาง **{d_name} (`{d_code}`)**?")
                    if st.button(f"🗑️ ลบ {d_code} ทันที", type="secondary", width="stretch", key="btn_del_shop_inline"):
                        if db.delete_shop(d_code):
                            if st.session_state.get("active_shop_code") == d_code:
                                st.session_state.pop("active_shop_code", None)
                                st.session_state.pop("global_upload_shop_select", None)
                                st.session_state.pop("sidebar_active_shop_dropdown", None)
                            st.toast(f"ลบช่องทาง {d_name} เรียบร้อยแล้ว", icon="🗑️")
                            st.rerun()
                        else:
                            st.error("ไม่สามารถลบร้านค้านี้ได้")
                else:
                    st.info("ℹ️ ไม่มีช่องทางย่อยที่สามารถลบได้ (ร้านที่ตั้งเป็น 'ร้านหลัก' หรือร้านสุดท้ายในระบบจะไม่สามารถลบได้ หากต้องการลบ กรุณาตั้งร้านอื่นเป็นร้านหลักก่อน)")

b_type = "★ ช่องทางหลัก" if active_shop_info.get("is_default") else "ช่องทางย่อย"
h_txt = f" ({active_shop_info.get('tiktok_handle')})" if active_shop_info.get("tiktok_handle") else ""
st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
                border: 1.5px solid #818cf8; border-radius: 14px; padding: 14px 20px; margin-top: 14px; margin-bottom: 20px;
                box-shadow: 0 4px 15px rgba(99, 102, 241, 0.08); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="width: 44px; height: 44px; border-radius: 12px; background: #4f46e5; color: white; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
                🏬
            </div>
            <div>
                <div style="font-size: 0.80rem; font-weight: 700; color: #4338ca; text-transform: uppercase; letter-spacing: 0.05em;">
                    กำลังทำงานในร้านค้า ({b_type})
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #1e1b4b;">
                    {active_shop_info.get('name')}{h_txt} <span style="font-size: 0.92rem; font-weight: 600; color: #6366f1;">(รหัส: {cur_selected_shop_code})</span>
                </div>
            </div>
        </div>
        <div style="background: #ffffff; border: 1px solid #c7d2fe; border-radius: 10px; padding: 7px 16px; font-size: 0.88rem; color: #4338ca; font-weight: 700;">
            📁 ไฟล์และผลการคำนวณจะถูกบันทึกเข้าสู่ร้านค้านี้
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_dual_upload, tab_from_data, tab_multi_upload = st.tabs(
    [
        "📤 1. อัปโหลดไฟล์ (Income + คำสั่งซื้อ) — แนะนำใช้งาน",
        "📂 2. เลือกจากโฟลเดอร์ data/ ในเครื่อง (ทางเลือกเสริม)",
        "📁 3. โยนไฟล์รวมหลายเดือน / ไฟล์ต้นทุนเดิม",
    ]
)

# --- โหมด 2: อัปโหลดไฟล์จากเครื่อง ---
with tab_dual_upload:
    with st.container(border=True):
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border: 1px solid #c7d2fe; border-radius: 14px; padding: 16px 20px; margin-bottom: 20px;">
                <div style="font-size: 1.1rem; font-weight: 800; color: #3730a3; display: flex; align-items: center; gap: 8px;">
                    💡 วิธีใช้งานง่ายๆ: วางไฟล์ลง 2 ช่องด้านล่าง แล้วกดปุ่มคำนวณทันที
                </div>
                <div style="font-size: 0.95rem; color: #4338ca; margin-top: 6px; line-height: 1.55;">
                    • <b>ช่องที่ 1 (ไฟล์คำสั่งซื้อ):</b> วางไฟล์ที่โหลดจากเมนู <i>"คำสั่งซื้อ"</i> ของ TikTok (ชื่อไฟล์ขึ้นต้นด้วย <code>ทั้งหมด คำสั่งซื้อ...</code>)<br>
                    • <b>ช่องที่ 2 (ไฟล์รายได้):</b> วางไฟล์ที่โหลดจากเมนู <i>"การเงิน/รายได้"</i> ของ TikTok (ชื่อไฟล์ขึ้นต้นด้วย <code>income_...</code>)<br>
                    • <b>คำแนะนำรอบนี้:</b> แนะนำให้ใส่ไฟล์คำสั่งซื้อ <b>{recommended_order_files} ไฟล์</b> {"(รอบแรกใส่ 2 เดือนติดกัน เช่น เดือน 8 + เดือน 9)" if repo_empty else "(รอบถัดไประบบดึงเดือนก่อนจากคลังให้เอง ใส่แค่เดือนใหม่ 1 ไฟล์พอ)"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        u_col1, u_col2 = st.columns(2, gap="medium")
        with u_col1:
            st.markdown(
                f"""
                <div style="background:#f8fafc; border: 1.5px dashed #6366f1; border-radius: 14px; padding: 14px 16px; margin-bottom: 12px;">
                    <div style="font-size: 1.05rem; font-weight: 800; color: #1e1b4b;">
                        📄 ช่องที่ 1: ไฟล์รายการคำสั่งซื้อ (Order)
                    </div>
                    <div style="font-size: 0.88rem; color: #475569; margin-top: 4px; line-height: 1.45;">
                        • โหลดจาก: หน้า <b>คำสั่งซื้อ (Orders)</b> ใน TikTok Shop<br>
                        • มีรายการสินค้าและจำนวนชิ้นที่ลูกค้าสั่งซื้อ เพื่อคิดราคาทุนสินค้า
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            files_order = st.file_uploader(
                "เลือกไฟล์คำสั่งซื้อ (ทั้งหมด คำสั่งซื้อ...xlsx) — ลากใส่ได้หลายไฟล์",
                type=["xlsx"],
                accept_multiple_files=True,
                key="uploader_orders",
                help="ไฟล์ที่มีชื่อขึ้นต้นด้วย 'ทั้งหมด คำสั่งซื้อ...' ดาวน์โหลดจากหน้า Orders ของ TikTok",
            )
            for fo in files_order or []:
                st.success(f"ตรวจพบ: `{fo.name}` ({fo.size / (1024*1024):.2f} MB)")
            if files_order:
                _check_order_count(len(files_order))

        with u_col2:
            st.markdown(
                """
                <div style="background:#f8fafc; border: 1.5px dashed #0ea5e9; border-radius: 14px; padding: 14px 16px; margin-bottom: 12px;">
                    <div style="font-size: 1.05rem; font-weight: 800; color: #082f49;">
                        💰 ช่องที่ 2: ไฟล์รายได้และการเงิน (Income)
                    </div>
                    <div style="font-size: 0.88rem; color: #475569; margin-top: 4px; line-height: 1.45;">
                        • โหลดจาก: หน้า <b>การเงิน > รายได้ (Finances / Settlements)</b> ใน TikTok Shop<br>
                        • มียอดเงินที่ TikTok โอนจริง และค่าธรรมเนียมต่างๆ
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            file_income = st.file_uploader(
                "เลือกไฟล์รายได้ (income_...xlsx) — 1 ไฟล์",
                type=["xlsx"],
                key="uploader_income",
                help="ไฟล์ที่มีชื่อขึ้นต้นด้วย 'income_...' ดาวน์โหลดจากหน้า Finances ของ TikTok",
            )
            if file_income:
                st.success(f"ตรวจพบ: `{file_income.name}` ({file_income.size / (1024*1024):.2f} MB)")

        can_process_dual = bool(files_order and file_income)
        if st.button(
            "⚙️ เริ่มคำนวณและสร้างไฟล์ต้นทุนรวมทันที (Calculate & Build Master Cost File)",
            type="primary",
            width="stretch",
            disabled=not can_process_dual,
            key="btn_process_dual",
        ):
            with st.spinner("กำลังอ่านชีต จับคู่รหัสสินค้า และคำนวณต้นทุน-กำไร..."):
                try:
                    _process_income_with_orders(
                        income_name=file_income.name,
                        income_bytes=file_income.getvalue(),
                        order_items=[(fo.name, fo.getvalue()) for fo in files_order],
                        use_repo=use_repo,
                        shop=active_shop_info,
                    )
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการประมวลผล: {e}")

# --- โหมด 1: อ่านจากโฟลเดอร์ data/ ---
with tab_from_data:
    with st.container(border=True):
        st.markdown("#### 📂 ตรวจพบไฟล์ในโฟลเดอร์ `data/`")
        col_d1, col_d2 = st.columns(2, gap="medium")

        with col_d1:
            st.markdown(f"📄 **1. ไฟล์รายการคำสั่งซื้อ (Order / OrderSKUList)** — แนะนำ {recommended_order_files} ไฟล์")
            if data_orders_files:
                order_names = [f["name"] for f in data_orders_files]
                # ค่าเริ่มต้น: ไฟล์ล่าสุดตามชื่อ (ชื่อไฟล์ TikTok มีวันที่ export) จำนวนตามคำแนะนำ
                default_orders = sorted(order_names, reverse=True)[:recommended_order_files]
                order_choices = st.multiselect(
                    "เลือกไฟล์คำสั่งซื้อจากโฟลเดอร์ data (เลือกได้หลายไฟล์):",
                    options=order_names,
                    default=default_orders,
                    key=f"sel_data_order_files_{recommended_order_files}",
                )
                for oc in order_choices:
                    info = next(f for f in data_orders_files if f["name"] == oc)
                    st.caption(f"• `data/{oc}` · {info['size_str']}")
                _check_order_count(len(order_choices))
            else:
                st.warning("⚠️ ไม่พบไฟล์คำสั่งซื้อในโฟลเดอร์ `data/` (ชื่อไฟล์ควรมีคำว่า 'คำสั่งซื้อ' หรือ 'Order')")
                order_choices = []

        with col_d2:
            st.markdown("💰 **2. ไฟล์รายได้และการเงิน (Income / รายละเอียดคำสั่งซื้อ)**")
            if data_income_files:
                income_choice = st.selectbox(
                    "เลือกไฟล์ Income จากโฟลเดอร์ data:",
                    options=[f["name"] for f in data_income_files],
                    index=0,
                    key="sel_data_income_file",
                )
                sel_income_info = next(f for f in data_income_files if f["name"] == income_choice)
                st.caption(f"ขนาดไฟล์: `{sel_income_info['size_str']}` · ตำแหน่ง: `data/{income_choice}`")
            else:
                st.warning("⚠️ ไม่พบไฟล์ Income ในโฟลเดอร์ `data/` (ชื่อไฟล์ควรมีคำว่า 'income' หรือ 'รายได้')")
                income_choice = None

        can_load_data = bool(order_choices and income_choice)
        b_load_data = st.button(
            "🚀 อ่านข้อมูลจากโฟลเดอร์ data และคำนวณต้นทุนทันที",
            type="primary",
            width="stretch",
            disabled=not can_load_data,
            key="btn_load_data_folder",
        )

        if b_load_data and can_load_data:
            with st.spinner("กำลังโหลดไฟล์จากโฟลเดอร์ data และคำนวณยอดชำระ-ต้นทุน-กำไร..."):
                try:
                    data_dir = get_data_dir()
                    _process_income_with_orders(
                        income_name=income_choice,
                        income_bytes=(data_dir / income_choice).read_bytes(),
                        order_items=[(oc, (data_dir / oc).read_bytes()) for oc in order_choices],
                        use_repo=use_repo,
                        shop=active_shop_info,
                    )
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")

# --- โหมด 3: โยนไฟล์รวมหลายเดือน / ไฟล์เดิม ---
with tab_multi_upload:
    with st.container(border=True):
        st.markdown("#### 📁 โยนไฟล์ Excel เดียวหรือหลายไฟล์พร้อมกัน")
        st.caption("รองรับไฟล์ต้นทุนเดิมที่มีชีตครบ หรือโยนหลายเดือนพร้อมกันเพื่อแยกงวดอัตโนมัติ")
        multi_files = st.file_uploader(
            "เลือกไฟล์ Excel (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            key="uploader_multi",
        )

        upload_mode = "auto"
        if multi_files and len(multi_files) > 1:
            mode_choice = st.radio(
                "รูปแบบการจัดการเมื่อโยนหลายไฟล์พร้อมกัน:",
                [
                    "⚡ อัตโนมัติ (แยกบันทึกเป็นรายเดือน/รายร้านให้อัตโนมัติ)",
                    "📅 แยกบันทึกเป็นคนละงวดตามแต่ละไฟล์",
                    "🔗 รวมทุกไฟล์ที่โยนเข้ามาเข้าเป็นงวดเดียวกัน",
                ],
                index=0,
                key="multi_mode_choice",
            )
            if mode_choice.startswith("📅"):
                upload_mode = "split"
            elif mode_choice.startswith("🔗"):
                upload_mode = "merge"

        if multi_files and st.button("⚙️ ประมวลผลไฟล์ทันที", type="primary", width="stretch", key="btn_process_multi"):
            with st.spinner("กำลังอ่านชีตและคำนวณต้นทุน-กำไร..."):
                try:
                    raw_payloads = [(f.name, f.getvalue()) for f in multi_files]
                    books = [load_workbook(BytesIO(raw_bytes), name=fname) for fname, raw_bytes in raw_payloads]

                    if is_admin():
                        for b in books:
                            if not b.sku.empty:
                                db.upsert_skus(
                                    b.sku.rename(
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
                                )

                    all_orders_frames = [b.orders for b in books if not b.orders.empty]
                    if all_orders_frames:
                        seq_o = []
                        for of in all_orders_frames:
                            of_c = of.copy()
                            sc = "SKU ID" if "SKU ID" in of_c.columns else "Seller SKU"
                            of_c["_line_seq"] = of_c.groupby([ORDER_KEY, sc], dropna=False).cumcount()
                            seq_o.append(of_c)
                        cat_o = pd.concat(seq_o, ignore_index=True)
                        sc = "SKU ID" if "SKU ID" in cat_o.columns else "Seller SKU"
                        shared_orders_pool = (
                            cat_o.drop_duplicates(subset=[ORDER_KEY, sc, "_line_seq"], keep="first")
                            .drop(columns=["_line_seq"])
                            .reset_index(drop=True)
                        )
                        db.add_missing_skus(extract_order_skus(shared_orders_pool))
                    else:
                        shared_orders_pool = pd.DataFrame()

                    sku_master = db.get_skus()
                    settle_books = [b for b in books if not b.settlement.empty]
                    usable_books = [b for b in books if (not b.settlement.empty or not b.orders.empty)]

                    should_split = False
                    if len(books) > 1:
                        if upload_mode == "split" and len(usable_books) > 1:
                            should_split = True
                        elif upload_mode == "auto":
                            if len(settle_books) >= 2 or (len(settle_books) == 0 and len(usable_books) >= 2):
                                should_split = True

                    if not should_split:
                        data = combine(books)
                        result = run_pipeline(data, sku_master)
                        period = detect_period_label(result, [fn for fn, _ in raw_payloads], shop=active_shop_info)

                        for fname, raw_bytes in raw_payloads:
                            db.save_uploaded_excel(
                                original_name=fname,
                                raw_bytes=raw_bytes,
                                period=period,
                                uploaded_by=user["username"],
                            )

                        if is_admin():
                            s_code = active_shop_info.get("code") if isinstance(active_shop_info, dict) else "matang"
                            _save_period_snapshot(period, result, shop_code=s_code)
                            db.set_app_state("active_period", period)

                        st.session_state.update(result=result, period=period, raw=data, notes=data.notes)
                        st.success(f"✅ คำนวณสำเร็จและบันทึกงวด **{period}** เรียบร้อยแล้ว")
                        st.rerun()
                    else:
                        saved_periods = []
                        last_res = None
                        all_notes = []
                        for fname, raw_bytes, b in zip(raw_payloads, books):
                            res_i = run_pipeline(b, sku_master)
                            p_name = detect_period_label(res_i, fname, shop=active_shop_info)
                            db.save_uploaded_excel(
                                original_name=fname,
                                raw_bytes=raw_bytes,
                                period=p_name,
                                uploaded_by=user["username"],
                            )
                            if is_admin():
                                s_code = active_shop_info.get("code") if isinstance(active_shop_info, dict) else "matang"
                                _save_period_snapshot(p_name, res_i, shop_code=s_code)
                            saved_periods.append(p_name)
                            all_notes.extend(f"[{fname}] {n}" for n in b.notes)
                            last_res = res_i

                        if is_admin() and len(saved_periods) >= 2:
                            combined_all = load_period_result(ALL_PERIODS_KEY)
                            db.set_app_state("active_period", ALL_PERIODS_KEY)
                            st.session_state.update(
                                result=combined_all if combined_all is not None else last_res,
                                period=ALL_PERIODS_KEY,
                                notes=all_notes,
                            )
                            st.success(f"✅ แยกบันทึกสำเร็จ **{len(saved_periods)} งวด**: {', '.join(saved_periods)}")
                            st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# สลับเลือกดูงวด / ดึงข้อมูล Snapshot ที่เคยบันทึกไว้
# ==============================================================================
snapshots = db.list_snapshots()
saved_months = snapshots["month"].tolist() if not snapshots.empty else []
cur_period = st.session_state.get("period", "")

if not snapshots.empty:
    with st.container(border=True):
        col_sel_p, col_btn_open, col_btn_del = st.columns([2.5, 1.0, 0.8], gap="small")
        view_options = [ALL_PERIODS_KEY] + saved_months if len(saved_months) >= 2 else saved_months
        
        # ป้องกัน widget จำคีย์ที่ถูกลบไปแล้ว
        if "active_snapshot_selector" in st.session_state and st.session_state["active_snapshot_selector"] not in view_options:
            st.session_state.pop("active_snapshot_selector", None)

        default_idx = view_options.index(cur_period) if cur_period in view_options else 0

        selected_snap = col_sel_p.selectbox(
            "📅 สลับเลือกดูข้อมูลงวดเดือน หรือ ดูสรุปรวมทุกงวด:",
            view_options,
            index=default_idx,
            key="active_snapshot_selector",
        )
        if col_btn_open.button("📂 เปิดดูข้อมูลนี้", type="primary", width="stretch", key="btn_open_snap"):
            loaded_res = load_period_result(selected_snap)
            if loaded_res is not None:
                db.set_app_state("active_period", selected_snap)
                st.session_state.update(result=loaded_res, period=selected_snap, notes=[])
                st.rerun()

        if is_admin() and col_btn_del.button("🗑️ ลบงวดนี้", type="secondary", width="stretch", key="btn_del_snap"):
            # ล้างคีย์ widget และแคชทั้งหมดที่อาจค้างอยู่ในหน่วยความจำ
            for k in (
                "active_snapshot_selector",
                "dash_period_sel",
                "adv_period_sel",
                "rep_period_sel",
                "global_period_sel",
                "_cached_master_excel_bytes",
                "_cached_master_excel_key",
                "_cached_rep_key",
                "_cached_rep_master_xlsx",
                "_cached_rep_xlsx",
            ):
                st.session_state.pop(k, None)

            if selected_snap == ALL_PERIODS_KEY:
                for m in saved_months:
                    db.delete_snapshot(m)
                for k in ("result", "period", "raw", "notes"):
                    st.session_state.pop(k, None)
                db.set_app_state("active_period", "")
                st.toast("ลบข้อมูลงวดทั้งหมดเรียบร้อยแล้ว", icon="🗑️")
            else:
                db.delete_snapshot(selected_snap)
                rem_snaps = db.list_snapshots()
                rem_months = rem_snaps["month"].tolist() if not rem_snaps.empty else []

                if not rem_months:
                    # ถ้าไม่มีงวดใดๆ เหลืออยู่เลยในระบบ ให้ล้างผลลัพธ์ออกทั้งหมด
                    for k in ("result", "period", "raw", "notes"):
                        st.session_state.pop(k, None)
                    db.set_app_state("active_period", "")
                else:
                    # ถ้ากำลังดูงวดที่ถูกลบ หรือสรุปรวมทุกงวด ให้สลับไปยังงวดที่ยังคงเหลืออยู่ทันที
                    if cur_period == selected_snap or cur_period == ALL_PERIODS_KEY or cur_period not in rem_months:
                        next_target = ALL_PERIODS_KEY if len(rem_months) >= 2 else rem_months[0]
                        new_res = load_period_result(next_target)
                        if new_res is not None:
                            db.set_app_state("active_period", next_target)
                            st.session_state.update(result=new_res, period=next_target, notes=[])
                        else:
                            for k in ("result", "period", "raw", "notes"):
                                st.session_state.pop(k, None)
                            db.set_app_state("active_period", "")
                    else:
                        # ถ้างวดที่กำลังดูอยู่คืองวดอื่นที่ไม่ได้โดนลบ ให้โหลดใหม่เพื่อให้แน่ใจว่าฐานข้อมูลอัปเดตตรงกัน
                        new_res = load_period_result(cur_period)
                        if new_res is not None:
                            st.session_state.update(result=new_res, period=cur_period, notes=[])

                st.toast(f"ลบงวด {selected_snap} เรียบร้อยแล้ว", icon="🗑️")
            st.rerun()

res = st.session_state.get("result")

# ถ้าระบบมี snapshot บันทึกไว้ แต่ใน session_state ว่างเปล่า ให้โหลดงวดล่าสุดอัตโนมัติ
if res is None and not snapshots.empty:
    saved_p = db.get_app_state("active_period")
    if saved_p == ALL_PERIODS_KEY and len(saved_months) >= 2:
        auto_target = ALL_PERIODS_KEY
    elif saved_p and saved_p in saved_months:
        auto_target = saved_p
    elif len(saved_months) >= 2:
        auto_target = ALL_PERIODS_KEY
    else:
        auto_target = saved_months[0]

    loaded_res = load_period_result(auto_target)
    if loaded_res is not None:
        db.set_app_state("active_period", auto_target)
        st.session_state.update(result=loaded_res, period=auto_target, notes=[])
        res = loaded_res

if res is None:
    st.info("💡 กรุณาเลือกอ่านข้อมูลจากโฟลเดอร์ data/ หรืออัปโหลดไฟล์ในส่วนที่ 1 เพื่อเริ่มดูข้อมูลและดาวน์โหลดไฟล์ต้นทุนรวม")
    st.stop()

cur_period = st.session_state.get("period", "ไม่ทราบงวด")
sku_master_df = db.get_skus()

# ตรวจสอบและคำนวณต้นทุนใหม่ทันทีถ้าฐานข้อมูล SKU มีการอัปเดตราคา
if res is not None and not res.missing_skus.empty and not sku_master_df.empty:
    missing_codes = set(res.missing_skus["sku"].astype(str).str.strip())
    filled = sku_master_df[sku_master_df["sku"].astype(str).str.strip().isin(missing_codes) & (sku_master_df["unit_cost"] > 0)]
    if not filled.empty:
        res = recalculate_with_skus(res, sku_master_df)
        st.session_state["result"] = res

orders_df = res.orders
order_lines_df = res.order_lines

# คำนวณสรุปงวด
fixed = db.total_fixed_cost(cur_period)
comm_pct = db.get_comm_pct(cur_period)
s_metric = summarize_for_period(res, cur_period) if cur_period else summarize(res, fixed_costs=fixed, comm_pct=comm_pct)


# ==============================================================================
# ส่วนที่ 2: การเลือกดูและตรวจสอบข้อมูล (Data View & Inspection Section)
# ==============================================================================
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); padding: 20px 26px; border-radius: 16px; margin-bottom: 22px; box-shadow: 0 4px 20px -2px rgba(2, 132, 199, 0.3); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div>
            <div style="display: inline-block; background: rgba(255, 255, 255, 0.2); color: #ffffff; font-size: 0.78rem; font-weight: 800; padding: 3px 10px; border-radius: 6px; letter-spacing: 0.05em; margin-bottom: 6px;">STEP 02</div>
            <h3 style="color: white; margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em;">🔍 ตรวจสอบตัวเลขและรายการคำสั่งซื้อ (Data Inspection)</h3>
            <p style="color: #e0f2fe; margin: 4px 0 0 0; font-size: 0.95rem;">
                ตรวจสอบยอดชำระเงิน (Col F), ต้นทุนรวม (Col G), กำไร (Col H), รายการสินค้า (Col I, J) และค้นหาข้อมูล
            </p>
        </div>
        <div style="font-size: 2.2rem; opacity: 0.9;">📊</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# KPI Cards
k1, k2, k3, k4 = st.columns(4, gap="medium")
sold_only = orders_df[orders_df["txn_type"] == "คำสั่งซื้อ"] if not orders_df.empty else orders_df
total_settlement = float(orders_df["net_settlement"].sum()) if not orders_df.empty else 0.0
total_cogs = float(orders_df["cogs"].sum()) if not orders_df.empty else 0.0
total_profit = float(orders_df["profit"].sum()) if not orders_df.empty else 0.0
total_sales = float(orders_df["net_sales"].sum()) if not orders_df.empty else 0.0
missing_sku_cnt = len(res.missing_skus) if not res.missing_skus.empty else 0

with k1:
    render_kpi_card(
        "1. เงินที่ TikTok โอนจริง (Col F)",
        baht(total_settlement),
        f"รายได้ยอดขายสุทธิ: {baht(total_sales)}",
        delta="เงินเข้าจริง",
        delta_positive=True,
        icon="💵",
    )
with k2:
    render_kpi_card(
        "2. ต้นทุนสินค้ารวม (Col G)",
        baht(total_cogs),
        f"คำสั่งซื้อ: {len(sold_only):,} ออเดอร์",
        delta="ทุนสินค้าขาย",
        icon="📦",
    )
with k3:
    margin_pct = (total_profit / total_sales * 100) if total_sales > 0 else 0.0
    render_kpi_card(
        "3. กำไรสุทธิแท้จริง (Col H)",
        baht(total_profit),
        f"คิดเป็น {margin_pct:.1f}% ของยอดขาย (F − G)",
        delta="กำไรสุทธิ" if total_profit >= 0 else "ขาดทุน",
        delta_positive=total_profit >= 0,
        icon="📈",
    )
with k4:
    render_kpi_card(
        "4. สินค้าที่ยังไม่มีราคาทุน",
        f"{missing_sku_cnt:,} ตัว",
        "ต้นทุนครบ 100% แม่นยำ" if missing_sku_cnt == 0 else "ต้องเพิ่มราคาทุนในหน้า SKU",
        delta="พร้อมส่งออก" if missing_sku_cnt == 0 else "ต้องตรวจ",
        delta_positive=missing_sku_cnt == 0,
        icon="✅" if missing_sku_cnt == 0 else "⚠️",
    )

# กล่องแจ้งเตือนและตารางกรอกราคาทุนสินค้าที่ขาดบนหน้าเว็บทันที
if missing_sku_cnt > 0 and not res.missing_skus.empty:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 2px solid #f59e0b; border-radius: 14px; padding: 18px 22px; margin-top: 15px; margin-bottom: 20px; box-shadow: 0 4px 14px -2px rgba(245, 158, 11, 0.2);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 2rem;">⚠️</span>
                    <div>
                        <h4 style="margin: 0; color: #92400e; font-size: 1.15rem; font-weight: 800;">
                            ตรวจพบ {missing_sku_cnt:,} สินค้าในคำสั่งซื้อที่ยังไม่มีราคาทุนในระบบ!
                        </h4>
                        <p style="margin: 4px 0 0 0; color: #b45309; font-size: 0.92rem;">
                            สินค้าเหล่านี้ถูกคำนวณต้นทุนเป็น 0 บาทชั่วคราว ทำให้กำไรสุทธิอาจสูงเกินจริง คุณสามารถพิมพ์ราคาทุนในตารางด้านล่างนี้ได้ทันที แล้วกด <b>"💾 บันทึกราคาทุนและคำนวณใหม่ทันที"</b>
                        </p>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander(f"✏️ เปิดช่องกรอกราคาทุนสินค้าที่ขาด ({missing_sku_cnt} รายการ) บนหน้าเว็บทันที", expanded=True):
        _render_missing_skus_editor(res, sku_master_df, cur_period, key_prefix="banner")

# แท็บเลือกดูข้อมูล
tab_v_settle, tab_v_orders, tab_v_sku, tab_v_withdraw, tab_v_fees = st.tabs(
    [
        "📑 1. รายละเอียดคำสั่งซื้อ (Settlement: F, G, H)",
        "📦 2. รายการสินค้า Order (ราคาต่อหน่วย I, มูลค่า J)",
        "⚠️ 3. ตรวจสอบราคาทุนสินค้า (SKU Master)",
        "🏦 4. บันทึกการถอนเงิน (Withdrawals)",
        "📋 5. สรุปค่าธรรมเนียม TikTok Shop",
    ]
)

with tab_v_settle:
    st.markdown("##### 📑 ตารางรายละเอียดคำสั่งซื้อ (คำนวณ Col F: ยอดชำระ, Col G: ต้นทุนรวม, Col H: กำไร แล้ว)")
    st.info(
        "💡 **คำอธิบาย:** แถวที่ขึ้น **ต้นทุนรวม (G) = 0** และ **ยอดชำระ (F) = 0** คือ **ออเดอร์ที่ลูกค้ายกเลิกคำสั่งซื้อ / ขอคืนเงินเต็มจำนวน** "
        "(ร้านค้าไม่ได้จัดส่งสินค้าจริง จึงไม่มีต้นทุนสินค้าสูญเสีย) — ระบบตั้งค่าเริ่มต้นให้แสดงเฉพาะคำสั่งซื้อที่มีการรับเงินและคำนวณต้นทุนจริง "
        "โดยสามารถสลับดูทั้งหมดได้ที่ตัวกรองด้านล่างครับ"
    )

    f_c1, f_c2, f_c3, f_c4 = st.columns([1.3, 1.4, 1.1, 1.2])
    with f_c1:
        search_oid = st.text_input("🔍 ค้นหาหมายเลขคำสั่งซื้อ:", placeholder="พิมพ์ Order ID...", key="search_oid_input")
    with f_c2:
        filter_profit = st.selectbox(
            "กรองสถานะคำสั่งซื้อ:",
            [
                "⭐ แสดงเฉพาะออเดอร์ที่มีการรับเงิน/คำนวณต้นทุน (ตัดออเดอร์ยกเลิกออก)",
                "แสดงทั้งหมด (รวมออเดอร์ยกเลิก 0 บาท)",
                "เฉพาะออเดอร์ที่มีกำไร (> 0)",
                "เฉพาะออเดอร์ที่ขาดทุน (< 0)",
                "เฉพาะออเดอร์ที่ยกเลิก/คืนเงินเต็มจำนวน (ยอด 0 บาท)",
                "เฉพาะรายการชำระค่าโฆษณา GMV",
            ],
            index=0,
            key="filter_profit_sel",
        )
    with f_c3:
        filter_txn = st.selectbox(
            "ประเภทธุรกรรม:",
            ["ทั้งหมด"] + (orders_df["txn_type"].unique().tolist() if not orders_df.empty else []),
            index=0,
            key="filter_txn_sel",
        )
    with f_c4:
        sort_by = st.selectbox(
            "จัดเรียงลำดับ:",
            [
                "ต้นทุนรวมมากสุด → น้อยสุด",
                "ยอดชำระมากสุด → น้อยสุด",
                "กำไรมากสุด → น้อยสุด",
                "ตามลำดับเดิมในไฟล์",
            ],
            index=0,
            key="sort_by_sel",
        )

    settle_display = company_settlement_view(orders_df)
    col_cogs = "ต้นทุนรวม (G)"
    col_settle = "ยอดการชำระเงินทั้งหมด (F)"
    col_profit = "กำไร (H = F - G)"

    if filter_profit.startswith("⭐"):
        if col_cogs in settle_display.columns and col_settle in settle_display.columns:
            settle_display = settle_display[(settle_display[col_settle] != 0) | (settle_display[col_cogs] != 0)]
    elif filter_profit == "เฉพาะออเดอร์ที่มีกำไร (> 0)":
        if col_profit in settle_display.columns:
            settle_display = settle_display[settle_display[col_profit] > 0]
    elif filter_profit == "เฉพาะออเดอร์ที่ขาดทุน (< 0)":
        if col_profit in settle_display.columns:
            settle_display = settle_display[settle_display[col_profit] < 0]
    elif filter_profit == "เฉพาะออเดอร์ที่ยกเลิก/คืนเงินเต็มจำนวน (ยอด 0 บาท)":
        if col_settle in settle_display.columns and col_cogs in settle_display.columns:
            settle_display = settle_display[(settle_display[col_settle] == 0) & (settle_display[col_cogs] == 0)]
    elif filter_profit == "เฉพาะรายการชำระค่าโฆษณา GMV":
        settle_display = settle_display[
            settle_display["ประเภทธุรกรรม"].astype(str).str.contains("GMV|โฆษณา", case=False, na=False)
        ]

    if filter_txn != "ทั้งหมด":
        settle_display = settle_display[settle_display["ประเภทธุรกรรม"] == filter_txn]

    if search_oid.strip():
        settle_display = settle_display[
            settle_display["หมายเลขคำสั่งซื้อ/การปรับ"].astype(str).str.contains(search_oid.strip(), case=False, na=False)
        ]

    if sort_by == "ต้นทุนรวมมากสุด → น้อยสุด" and col_cogs in settle_display.columns:
        settle_display = settle_display.sort_values(col_cogs, ascending=False)
    elif sort_by == "ยอดชำระมากสุด → น้อยสุด" and col_settle in settle_display.columns:
        settle_display = settle_display.sort_values(col_settle, ascending=False)
    elif sort_by == "กำไรมากสุด → น้อยสุด" and col_profit in settle_display.columns:
        settle_display = settle_display.sort_values(col_profit, ascending=False)

    if not is_admin():
        settle_display = settle_display.drop(
            columns=[c for c in (col_settle, col_cogs, col_profit) if c in settle_display.columns],
            errors="ignore",
        )
    st.dataframe(settle_display, width="stretch", hide_index=True, height=380)
    st.caption(f"แสดงผล {len(settle_display):,} รายการ จากทั้งหมด {len(orders_df):,} รายการ")

with tab_v_orders:
    st.markdown("##### 📦 ตารางรายการสินค้าในออเดอร์ (คำนวณ Col I: ราคาต่อหน่วย, Col J: มูลค่าต้นทุน แล้ว)")
    ord_display = company_order_lines_view(order_lines_df)
    if ord_display.empty:
        st.info("ไม่มีข้อมูลในชีต Order")
    else:
        search_sku = st.text_input("🔍 ค้นหาตาม Seller SKU หรือชื่อสินค้า:", placeholder="พิมพ์ SKU หรือชื่อ...", key="search_sku_input")
        if search_sku.strip():
            mask = (
                ord_display["Seller SKU"].astype(str).str.contains(search_sku.strip(), case=False, na=False)
                | ord_display["Product Name"].astype(str).str.contains(search_sku.strip(), case=False, na=False)
            )
            ord_display = ord_display[mask]

        if not is_admin():
            ord_display = ord_display.drop(columns=[c for c in ("ราคาต่อหน่วย", "มูลค่า") if c in ord_display.columns], errors="ignore")
        st.dataframe(ord_display, width="stretch", hide_index=True, height=380)
        st.caption(f"แสดงผล {len(ord_display):,} แถวสินค้า จากทั้งหมด {len(order_lines_df):,} แถว")

with tab_v_sku:
    st.markdown("##### ⚠️ ตารางราคาทุนสินค้า (SKU Master)")
    if not res.missing_skus.empty:
        st.warning(f"⚠️ พบ **{len(res.missing_skus):,} สินค้า** ที่ยังไม่มีราคาทุนในระบบ (ระบบใช้ต้นทุน 0.0 ชั่วคราว)")
        _render_missing_skus_editor(res, sku_master_df, cur_period, key_prefix="tab")
    else:
        st.success("✅ สินค้าทุกรหัสในงวดนี้มีราคาทุนครบ 100%")

    with st.expander("📦 ดูและค้นหาฐานข้อมูลราคาทุนสินค้าทั้งหมดในระบบ", expanded=False):
        st.dataframe(
            sku_master_df[["sku", "name", "category", "unit_cost", "retail_price", "promo_price", "list_price"]].rename(
                columns={
                    "sku": "รหัส",
                    "name": "ชื่อสินค้า",
                    "category": "หมวดหมู่",
                    "unit_cost": "ราคาทุน",
                    "retail_price": "ราคาปลีก",
                    "promo_price": "ราคาโปร",
                    "list_price": "ราคาตั้งขาย",
                }
            ),
            width="stretch",
            hide_index=True,
            height=300,
        )
        st.page_link("pages/3_📦_สินค้าและต้นทุน.py", label="ไปหน้าจัดการและแก้ไขราคาทุนสินค้า →", icon="📦")

with tab_v_withdraw:
    st.markdown("##### 🏦 รายการบันทึกการถอนเงินเข้าบัญชีธนาคาร")
    if res.withdrawals is not None and not res.withdrawals.empty:
        st.dataframe(res.withdrawals, width="stretch", hide_index=True, height=350)
        st.caption(f"รวม {len(res.withdrawals):,} รายการถอนเงิน ยอดรวม: {baht(res.withdrawals['จำนวน'].sum() if 'จำนวน' in res.withdrawals.columns else 0)}")
    else:
        st.info("ไม่มีข้อมูลบันทึกการถอนในไฟล์ที่นำเข้า")

with tab_v_fees:
    st.markdown("##### 📋 รายละเอียดค่าธรรมเนียม TikTok Shop ตามโครงสร้างทางการ")
    fee_table = tiktok_report_table(res)
    if not fee_table.empty:
        st.dataframe(fee_table, width="stretch", hide_index=True, height=350)
    else:
        st.info("ไม่มีรายละเอียดค่าธรรมเนียม")

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# ส่วนที่ 3: การส่งออกข้อมูล (Export Section)
# ==============================================================================
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); padding: 20px 26px; border-radius: 16px; margin-bottom: 22px; box-shadow: 0 4px 20px -2px rgba(124, 58, 237, 0.3); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div>
            <div style="display: inline-block; background: rgba(255, 255, 255, 0.2); color: #ffffff; font-size: 0.78rem; font-weight: 800; padding: 3px 10px; border-radius: 6px; letter-spacing: 0.05em; margin-bottom: 6px;">STEP 03</div>
            <h3 style="color: white; margin: 0; font-size: 1.35rem; font-weight: 800; letter-spacing: -0.01em;">🎯 ส่งออกไฟล์ต้นทุนรวมฉบับสมบูรณ์ (Export Master File)</h3>
            <p style="color: #f3e8ff; margin: 4px 0 0 0; font-size: 0.95rem;">
                ดาวน์โหลดไฟล์ต้นทุนรวมฉบับสมบูรณ์ 7 ชีตตรงมาตรฐานบริษัท หรือบันทึกลงโฟลเดอร์ <code>data/</code> ทันที
            </p>
        </div>
        <div style="font-size: 2.2rem; opacity: 0.9;">🚀</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# พระเอกของระบบ: กล่องส่งออกไฟล์ต้นทุนรวมฉบับสมบูรณ์
default_cost_filename = format_thai_cost_filename(cur_period)

with st.container(border=True):
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%); border: 1.5px solid #6ee7b7; border-radius: 16px; padding: 18px 24px; margin-bottom: 20px;">
            <div style="font-size: 1.25rem; font-weight: 800; color: #065f46; margin-bottom: 8px;">
                🎯 ไฟล์ต้นทุนรวมฉบับสมบูรณ์ (Master Cost File — ครบทั้ง 7 ชีตตามมาตรฐานบริษัท 100%)
            </div>
            <div style="font-size: 0.95rem; color: #047857; line-height: 1.6;">
                ไฟล์ที่ดาวน์โหลดออกมานี้สามารถนำไปใช้งานต่อหรือส่งให้ฝ่ายบัญชีได้ทันที โดยประกอบด้วยชีตครบถ้วน:
                <br>• 📑 <b>รายละเอียดคำสั่งซื้อ:</b> คำนวณเงินรับสุทธิ (Col F), ต้นทุนสินค้าจริง (Col G), กำไรสุทธิ (Col H) รายออเดอร์ครบถ้วน
                <br>• 📦 <b>SKU:</b> ฐานข้อมูลราคาทุนสินค้าทุกรหัสจากระบบ
                <br>• 🚚 <b>Order ล่าสุด & Order ก่อนหน้า:</b> แยกชีตคำสั่งซื้อ 2 เดือนติดกัน พร้อมราคาต่อหน่วย (Col I) และมูลค่าต้นทุน (Col J)
                <br>• 📋 <b>รายงาน, บันทึกการถอน, คำอธิบายค่าธรรมเนียม:</b> ข้อมูลทางการเงิน TikTok Shop ครบถ้วน
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    exp_col_name, exp_col_dl, exp_col_save = st.columns([2.0, 1.4, 1.4], gap="medium")
    with exp_col_name:
        custom_cost_name = st.text_input(
            "ชื่อไฟล์ต้นทุนรวมที่ต้องการส่งออก (.xlsx):",
            value=default_cost_filename,
            key="input_export_cost_filename",
            help="สามารถแก้ไขชื่อไฟล์ได้ เช่น ต้นทุน2569-09.xlsx หรือ ต้นทุนดีไวน์2569-09.xlsx",
        ).strip()
        if not custom_cost_name.endswith(".xlsx"):
            custom_cost_name += ".xlsx"

    # จัดการไฟล์ Excel ต้นทุนรวม (Lazy-load & Cache เพื่อไม่ให้หน้าเว็บค้างหรือช้า)
    excel_cache_key = f"{cur_period}_{len(res.orders)}_{len(sku_master_df)}"
    has_cached = (
        st.session_state.get("_cached_master_excel_key") == excel_cache_key
        and st.session_state.get("_cached_master_excel_bytes") is not None
    )

    with exp_col_dl:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if has_cached:
            st.download_button(
                label=f"⬇️ ดาวน์โหลดไฟล์ต้นทุนรวม ({custom_cost_name})",
                data=st.session_state["_cached_master_excel_bytes"],
                file_name=custom_cost_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
                key="btn_download_master_cost",
            )
        else:
            if st.button(
                f"⚡ 1-Click ประกอบไฟล์ต้นทุนรวม ({custom_cost_name})",
                type="primary",
                width="stretch",
                key="btn_generate_master_cost",
                help="กดเพื่อสร้างไฟล์ Excel 7 ชีตสมบูรณ์พร้อมสูตร SUM",
            ):
                with st.spinner("กำลังประกอบไฟล์ต้นทุนรวม 7 ชีต (ใส่สูตร SUM และผูกข้อมูลทุกแถว)..."):
                    b = build_company_cost_master_excel(
                        res=res,
                        sku_master=sku_master_df,
                        period_label=cur_period,
                    )
                    st.session_state["_cached_master_excel_bytes"] = b
                    st.session_state["_cached_master_excel_key"] = excel_cache_key
                    st.rerun()

    with exp_col_save:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if has_cached:
            if st.button(f"💾 บันทึกสำเนาลงโฟลเดอร์ data/", width="stretch", key="btn_save_to_data_folder"):
                try:
                    dest_dir = get_data_dir()
                    dest_path = dest_dir / custom_cost_name
                    dest_path.write_bytes(st.session_state["_cached_master_excel_bytes"])
                    st.toast(f"บันทึกไฟล์ {custom_cost_name} ลงใน {dest_dir} เรียบร้อยแล้ว!")
                    st.success(f"✅ บันทึกไฟล์สำเร็จ: `{dest_path}` ({len(st.session_state['_cached_master_excel_bytes']) / (1024*1024):.2f} MB)")
                except Exception as e:
                    st.error(f"ไม่สามารถบันทึกไฟล์ลงโฟลเดอร์ data: {e}")
        else:
            st.button("💾 บันทึกสำเนาลง data/", disabled=True, width="stretch", key="btn_save_disabled", help="กรุณากดปุ่มสร้างไฟล์ก่อนบันทึก")

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# กล่องส่งออกรายงานอื่นๆ
with st.container(border=True):
    st.markdown("### 📊 2. ส่งออกรายงานผู้บริหารและสรุปงบกำไรขาดทุน")
    r_col1, r_col2 = st.columns(2, gap="medium")

    file_tag = "รวมทุกงวด" if cur_period == ALL_PERIODS_KEY else cur_period
    cat_df = by_category(res)
    sku_df = by_sku(res)

    export_report_sheets = {
        "รายงานตามโครงสร้าง TikTok": tiktok_report_table(res),
        "สรุปราย SKU": sku_df,
        "ตามหมวดหมู่": cat_df,
        "รายละเอียดคำสั่งซื้อ": company_settlement_view(orders_df),
        "Order": company_order_lines_view(order_lines_df),
        "SKU ไม่มีราคาทุน": res.missing_skus,
    }
    if not res.withdrawals.empty:
        export_report_sheets["บันทึกการถอน"] = res.withdrawals

    report_excel_bytes = to_excel(s_metric, export_report_sheets)

    with r_col1:
        st.download_button(
            label=f"📗 ดาวน์โหลดรายงานสรุป Excel ทุกชีต (รายงานต้นทุนกำไร_{file_tag}.xlsx)",
            data=report_excel_bytes,
            file_name=f"รายงานต้นทุนกำไร_{file_tag}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            key="btn_download_report_excel",
        )

    with r_col2:
        top_sku = (
            sku_df.sort_values("ยอดขายหลังส่วนลด", ascending=False).head(10)[
                ["สถานะ", "SKU", "ชื่อสินค้า", "จำนวนขาย", "ยอดขายหลังส่วนลด", "กำไรขั้นต้น"]
            ]
            if not sku_df.empty
            else sku_df
        )
        html_report = to_html_report(s_metric, file_tag, cat_df, top_sku)
        st.download_button(
            label=f"📕 ดาวน์โหลดรายงานผู้บริหาร 1 หน้า HTML/PDF ({file_tag})",
            data=html_report.encode("utf-8"),
            file_name=f"รายงานผู้บริหาร_{file_tag}.html",
            mime="text/html",
            width="stretch",
            key="btn_download_report_html",
        )
