from core.reloader import ensure_fresh

ensure_fresh()

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from core import db
from core.export import company_order_lines_view, company_settlement_view
from core.loader import LoadedWorkbook, ORDER_KEY, SETTLEMENT_KEY, load_workbook
from core.metrics import summarize
from core.pipeline import (
    ALL_PERIODS_KEY,
    combine,
    detect_period_label,
    extract_order_skus,
    run_pipeline,
)
from core.ui import (
    baht,
    init_page,
    is_admin,
    load_period_result,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
)

init_page("นำเข้าข้อมูล", "📤")
user = require_login()

render_page_header("นำเข้าข้อมูล Excel (โยนไฟล์คำนวณและแยกงวดอัตโนมัติ)", period=st.session_state.get("period"))


def _save_period_snapshot(period_name: str, res_obj) -> None:
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
    )


col_upload, col_history = st.columns([1.4, 1.0], gap="medium")

with col_upload:
    with st.container(border=True):
        render_section_header("อัปโหลดไฟล์ Excel (.xlsx) — โยนไฟล์เดียวหรือหลายเดือนพร้อมกันได้ทันที", icon="📂")
        st.caption(
            "รองรับชีต `SKU`, `รายละเอียดคำสั่งซื้อ`, `Order8 / Order7 / OrderSKUList`, `บันทึกการถอน` และ `ads` "
            "— ระบบจะดึงราคาทุน คำนวณยอดชำระ-ต้นทุน-กำไร และบันทึกแยกเดือนให้อัตโนมัติทันที"
        )
        files = st.file_uploader("เลือกหรือลากไฟล์ Excel มาวางที่นี่ (เลือกหลายไฟล์พร้อมกันได้)", type=["xlsx"], accept_multiple_files=True)

        upload_mode = "auto"
        if files and len(files) > 1:
            mode_choice = st.radio(
                "รูปแบบการจัดการเมื่อโยนหลายไฟล์พร้อมกัน:",
                [
                    "⚡ อัตโนมัติ (แนะนำ — แยกบันทึกเป็นรายเดือน/รายร้านให้อัตโนมัติ และจับคู่ไฟล์แยก Settlement+Order ให้เอง)",
                    "📅 แยกบันทึกเป็นคนละงวดตามแต่ละไฟล์",
                    "🔗 รวมทุกไฟล์ที่โยนเข้ามาเข้าเป็นงวดเดียวกัน",
                ],
                index=0,
            )
            if mode_choice.startswith("📅"):
                upload_mode = "split"
            elif mode_choice.startswith("🔗"):
                upload_mode = "merge"

        if files and st.button("⚙️ คำนวณและบันทึกข้อมูลทันที", type="primary", width="stretch"):
            with st.spinner("กำลังอ่านชีต จับคู่รหัส SKU คำนวณยอดชำระ-ต้นทุน-กำไร และบันทึกงวดอัตโนมัติ..."):
                try:
                    raw_payloads = [(f.name, f.getvalue()) for f in files]
                    books = [load_workbook(BytesIO(raw_bytes), name=fname) for fname, raw_bytes in raw_payloads]

                    # 1. นำเข้าตาราง SKU จากทุกไฟล์ก่อน เพื่อให้ฐานข้อมูลราคาทุนครบสมบูรณ์ที่สุด
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

                    # 2. รวมชีต Order จากทุกไฟล์ที่โยนเข้ามาเพื่อดึง SKU ตกหล่น และช่วยจับคู่ออเดอร์ข้ามเดือนอัตโนมัติ
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

                    # 3. ตัดสินใจว่าจะแยกงวดตามไฟล์ หรือรวมเป็นงวดเดียว
                    settle_books = [b for b in books if not b.settlement.empty]
                    usable_books = [b for b in books if (not b.settlement.empty or not b.orders.empty)]

                    should_split = False
                    if len(books) > 1:
                        if upload_mode == "split" and len(usable_books) > 1:
                            should_split = True
                        elif upload_mode == "auto":
                            # ถ้ามีไฟล์ที่มีรายละเอียดคำสั่งซื้อตั้งแต่ 2 ไฟล์ขึ้นไป (เช่น โยนหลายเดือน หรือ 2 ร้านพร้อมกัน) ให้แยกงวดอัตโนมัติ
                            # หรือถ้าไม่มีไฟล์ไหนมี settlement เลยแต่มีไฟล์ Order หลายเดือน ก็แยกงวดให้เช่นกัน
                            if len(settle_books) >= 2 or (len(settle_books) == 0 and len(usable_books) >= 2):
                                should_split = True

                    if not should_split:
                        data = combine(books)
                        result = run_pipeline(data, sku_master)
                        period = detect_period_label(result, [fn for fn, _ in raw_payloads])

                        for fname, raw_bytes in raw_payloads:
                            db.save_uploaded_excel(
                                original_name=fname,
                                raw_bytes=raw_bytes,
                                period=period,
                                uploaded_by=user["username"],
                            )

                        if is_admin():
                            _save_period_snapshot(period, result)
                            db.set_app_state("active_period", period)

                        st.session_state.update(result=result, period=period, raw=data, notes=data.notes)
                        save_msg = f" และบันทึกงวด **{period}** ลงระบบเรียบร้อยแล้ว" if is_admin() else ""
                        st.success(
                            f"✅ คำนวณสำเร็จ: {len(result.orders):,} รายการในรายละเอียดคำสั่งซื้อ · "
                            f"{len(result.order_lines):,} รายการในชีต Order{save_msg}"
                        )
                    else:
                        target_items: list[tuple[str, bytes, LoadedWorkbook]] = []
                        target_settle_only = len(settle_books) >= 2
                        for (fname, raw_bytes), b in zip(raw_payloads, books):
                            if target_settle_only and not b.settlement.empty:
                                target_items.append((fname, raw_bytes, b))
                            elif not target_settle_only and (not b.settlement.empty or not b.orders.empty):
                                target_items.append((fname, raw_bytes, b))
                            else:
                                # ไฟล์เสริม เช่น ไฟล์ SKU ล้วน หรือ Order เดือนก่อนหน้า เก็บสำเนาไว้ด้วย
                                db.save_uploaded_excel(
                                    original_name=fname,
                                    raw_bytes=raw_bytes,
                                    period="ไฟล์ประกอบ",
                                    uploaded_by=user["username"],
                                )

                        saved_periods: list[str] = []
                        all_notes: list[str] = []
                        used_names: set[str] = set()
                        last_res = None

                        for fname, raw_bytes, b in target_items:
                            # เติมรายการ Order ข้ามเดือนจากไฟล์อื่นที่โยนมาพร้อมกัน (เฉพาะ Order ID ที่อยู่ใน Settlement ของไฟล์นี้)
                            wb_work = LoadedWorkbook(
                                name=b.name,
                                settlement=b.settlement,
                                orders=b.orders,
                                ads=b.ads,
                                sku=b.sku,
                                withdrawals=b.withdrawals,
                                notes=list(b.notes),
                            )
                            if not wb_work.settlement.empty and not shared_orders_pool.empty:
                                settle_ids = set(wb_work.settlement[SETTLEMENT_KEY].astype(str).str.strip())
                                extra_o = shared_orders_pool[shared_orders_pool[ORDER_KEY].astype(str).isin(settle_ids)]
                                if not extra_o.empty:
                                    seq_pair = []
                                    for of in (wb_work.orders, extra_o):
                                        if not of.empty:
                                            of_c = of.copy()
                                            sc = "SKU ID" if "SKU ID" in of_c.columns else "Seller SKU"
                                            of_c["_line_seq"] = of_c.groupby([ORDER_KEY, sc], dropna=False).cumcount()
                                            seq_pair.append(of_c)
                                    merged_o = pd.concat(seq_pair, ignore_index=True)
                                    sc = "SKU ID" if "SKU ID" in merged_o.columns else "Seller SKU"
                                    wb_work.orders = (
                                        merged_o.drop_duplicates(subset=[ORDER_KEY, sc, "_line_seq"], keep="first")
                                        .drop(columns=["_line_seq"])
                                        .reset_index(drop=True)
                                    )

                            res_i = run_pipeline(wb_work, sku_master)
                            p_name = detect_period_label(res_i, fname)
                            if p_name in used_names:
                                stem = Path(fname).stem[:24]
                                p_name = f"{p_name} ({stem})"
                            used_names.add(p_name)

                            db.save_uploaded_excel(
                                original_name=fname,
                                raw_bytes=raw_bytes,
                                period=p_name,
                                uploaded_by=user["username"],
                            )
                            if is_admin():
                                _save_period_snapshot(p_name, res_i)

                            saved_periods.append(p_name)
                            all_notes.extend(f"[{fname}] {n}" for n in wb_work.notes)
                            last_res = res_i

                        if is_admin() and len(saved_periods) >= 2:
                            combined_all = load_period_result(ALL_PERIODS_KEY)
                            db.set_app_state("active_period", ALL_PERIODS_KEY)
                            st.session_state.update(
                                result=combined_all if combined_all is not None else last_res,
                                period=ALL_PERIODS_KEY,
                                notes=all_notes,
                            )
                            st.success(
                                f"✅ คำนวณและแยกบันทึกสำเร็จ **{len(saved_periods)} งวด**: "
                                f"{', '.join(saved_periods)} — ตอนนี้เปิดมุมมอง **📊 สรุปรวมทุกงวดทั้งหมด** ให้แล้ว "
                                "(สลับดูแยกแต่ละเดือนได้ที่เมนูด้านขวาหรือหน้าแดชบอร์ดทันที)"
                            )
                        elif last_res is not None:
                            p_final = saved_periods[-1]
                            if is_admin():
                                db.set_app_state("active_period", p_final)
                            st.session_state.update(result=last_res, period=p_final, notes=all_notes)
                            st.success(f"✅ คำนวณและบันทึกงวด **{p_final}** สำเร็จ!")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

with col_history:
    with st.container(border=True):
        render_section_header("เลือกดูแยกตามเดือน หรือ สรุปรวมทั้งหมด", icon="🗂️")
        snapshots = db.list_snapshots()
        if snapshots.empty:
            st.caption("ยังไม่มีข้อมูลงวดที่บันทึกไว้ กรุณาโยนไฟล์ Excel ด้านซ้าย ระบบจะบันทึกให้อัตโนมัติทันที")
        else:
            saved_months = snapshots["month"].tolist()
            order_map = dict(zip(snapshots["month"], snapshots["order_count"]))
            view_options = [ALL_PERIODS_KEY] + saved_months
            cur_p = st.session_state.get("period", "")
            default_idx = view_options.index(cur_p) if cur_p in view_options else 0

            selected_snap = st.selectbox(
                "เลือกงวดเดือน หรือ สรุปรวมทุกงวด:",
                view_options,
                index=default_idx,
                format_func=lambda m: (
                    f"📊 สรุปรวมทุกงวดทั้งหมด ({len(saved_months)} งวด)"
                    if m == ALL_PERIODS_KEY
                    else f"📅 งวด {m} ({int(order_map.get(m, 0)):,} ออเดอร์)"
                ),
            )
            b_open, b_del = st.columns([1.5, 1])
            if b_open.button("📂 เปิดดูข้อมูลนี้", type="primary", width="stretch"):
                loaded_res = load_period_result(selected_snap)
                if loaded_res is not None:
                    db.set_app_state("active_period", selected_snap)
                    st.session_state.update(result=loaded_res, period=selected_snap, notes=[])
                    st.rerun()
            if (
                is_admin()
                and selected_snap != ALL_PERIODS_KEY
                and b_del.button("🗑️ ลบงวดนี้", type="secondary", width="stretch")
            ):
                db.delete_snapshot(selected_snap)
                if st.session_state.get("period") in (selected_snap, ALL_PERIODS_KEY):
                    for k in ("result", "period", "raw", "notes"):
                        st.session_state.pop(k, None)
                st.toast(f"ลบงวด {selected_snap} แล้ว")
                st.rerun()

            if is_admin():
                st.divider()
                q1, q2 = st.columns(2)
                q1.page_link("pages/1_📊_แดชบอร์ด.py", label="ไปหน้าแดชบอร์ด →", icon="📊", width="stretch")
                q2.page_link("pages/5_📑_รายงาน.py", label="ไปหน้ารายงาน →", icon="📑", width="stretch")

# กล่องแสดงและดาวน์โหลดสำเนาไฟล์ Excel ต้นฉบับที่เคยอัปโหลดไว้ใน data/uploads/
uploads_df = db.list_uploaded_excels()
if not uploads_df.empty:
    with st.expander(f"📁 สำเนาไฟล์ Excel ต้นฉบับที่เก็บไว้ในเครื่อง ({len(uploads_df)} ไฟล์ — โฟลเดอร์ data/uploads/)", expanded=False):
        sel_col, dl_col, del_col = st.columns([2.5, 1.2, 0.9])
        selected_id = sel_col.selectbox(
            "เลือกไฟล์สำเนา:",
            uploads_df["id"].tolist(),
            label_visibility="collapsed",
            format_func=lambda fid: (
                f"[{uploads_df.loc[uploads_df['id'] == fid, 'period'].values[0] or '-'}] "
                f"{uploads_df.loc[uploads_df['id'] == fid, 'original_name'].values[0]} "
                f"({uploads_df.loc[uploads_df['id'] == fid, 'size_bytes'].values[0] / 1024:,.0f} KB · "
                f"อัปโหลด {uploads_df.loc[uploads_df['id'] == fid, 'uploaded_at'].values[0]})"
            ),
        )
        found = db.get_uploaded_excel_path(selected_id)
        if found:
            orig_name, file_path = found
            dl_col.download_button(
                "⬇️ ดาวน์โหลดไฟล์ต้นฉบับ",
                file_path.read_bytes(),
                file_name=orig_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        if is_admin() and del_col.button("🗑️ ลบสำเนา", width="stretch"):
            db.delete_uploaded_excel(selected_id)
            st.toast("ลบไฟล์สำเนาเรียบร้อยแล้ว")
            st.rerun()

res = st.session_state.get("result")
if res is None:
    st.stop()

cur_period = st.session_state.get("period", "ไม่ทราบงวด")
o = res.orders
notes = st.session_state.get("notes", [])

if notes:
    st.caption("ชีตที่ตรวจพบ: " + " · ".join(notes))

c1, c2, c3, c4 = st.columns(4, gap="medium")
sold_only = o[o["txn_type"] == "คำสั่งซื้อ"]
order_only_h = float(sold_only["profit"].sum()) if not sold_only.empty else float(o["profit"].sum())
net_h = float(o["profit"].sum())
with c1:
    render_kpi_card("ยอดการชำระเงินทั้งหมด (F)", baht(o["net_settlement"].sum()), f"รายได้ทั้งหมด {baht(o['net_sales'].sum())}", icon="💵")
with c2:
    render_kpi_card("ต้นทุนสินค้ารวม (G)", baht(o["cogs"].sum()), f"คำสั่งซื้อ {len(sold_only):,} รายการ", icon="📦")
with c3:
    h_note = f"ก่อนโฆษณา GMV: {baht(order_only_h)}" if abs(order_only_h - net_h) >= 1 else "ยอดชำระ (F) − ต้นทุนรวม (G)"
    render_kpi_card("กำไรหลังหักโฆษณา GMV (H สุทธิ)", baht(net_h), h_note, delta_positive=net_h >= 0, icon="📊")
with c4:
    miss_cnt = len(res.missing_skus)
    render_kpi_card("SKU ที่ยังไม่มีราคาทุน", f"{miss_cnt:,} รหัส", "พร้อมคำนวณครบ" if miss_cnt == 0 else "ควรเพิ่มราคาทุน", icon="✅" if miss_cnt == 0 else "⚠️")

if is_admin() and cur_period != ALL_PERIODS_KEY:
    with st.expander("✏️ เปลี่ยนชื่องวด หรือ บันทึกซ้ำในชื่องวดอื่น (เช่น แยกชื่อร้าน)", expanded=False):
        s_col1, s_col2 = st.columns([1.4, 1.2], gap="small")
        save_name = s_col1.text_input(
            "ชื่องวดที่จะบันทึก:",
            value=cur_period,
            placeholder="เช่น 2026-08 (ร้านหลัก) หรือ 2026-08 (ดีไวน์)",
        ).strip().replace("/", "-")
        s_col2.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
        if s_col2.button(f"💾 บันทึกเป็นงวด '{save_name}'", type="primary", width="stretch") and save_name:
            _save_period_snapshot(save_name, res)
            db.set_app_state("active_period", save_name)
            st.session_state["period"] = save_name
            st.success(f"บันทึกงวด '{save_name}' เรียบร้อยแล้ว!")
            st.rerun()

if not res.missing_skus.empty:
    with st.container(border=True):
        render_section_header("รายการสินค้าที่ยังไม่มีราคาทุน (แทนค่า #N/A เดิมใน Excel)", icon="⚠️")
        st.dataframe(
            res.missing_skus.rename(columns={"sku": "รหัส", "name": "ชื่อ", "category": "หมวดหมู่", "qty": "จำนวนขายสุทธิ"}),
            width="stretch",
            hide_index=True,
        )

with st.container(border=True):
    t_settle, t_ord = st.tabs(
        [
            "📑 ชีต 'รายละเอียดคำสั่งซื้อ' (คำนวณ F=ยอดชำระ, G=ต้นทุนรวม, H=กำไร แล้ว)",
            "📦 ชีต 'Order' (คำนวณ I=ราคาต่อหน่วย, J=มูลค่า แล้ว)",
        ]
    )
    with t_settle:
        settle_view = company_settlement_view(o)
        if not is_admin():
            settle_view = settle_view.drop(
                columns=[c for c in ("ยอดการชำระเงินทั้งหมด (F)", "ต้นทุนรวม (G)", "กำไร (H = F - G)") if c in settle_view.columns]
            )
        st.dataframe(settle_view, width="stretch", hide_index=True, height=400)
    with t_ord:
        ord_view = company_order_lines_view(res.order_lines)
        if ord_view.empty:
            st.caption("ไม่มีข้อมูลจากชีต Order")
        else:
            if not is_admin():
                ord_view = ord_view.drop(columns=[c for c in ("ราคาต่อหน่วย", "มูลค่า") if c in ord_view.columns])
            st.dataframe(ord_view, width="stretch", hide_index=True, height=400)
