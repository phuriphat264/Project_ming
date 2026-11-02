"""ส่งออกรายงานเป็น Excel (.xlsx) และ HTML/PDF ตามโครงสร้างคอลัมน์มาตรฐานของ TikTok Shop และบริษัท"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re

import pandas as pd

from .loader import FEE_DESCRIPTIONS
from .metrics import Summary
from .pipeline import ensure_order_columns

ORDER_COL_TH = {
    "order_id": "หมายเลขคำสั่งซื้อ/การปรับ",
    "txn_type": "ประเภทธุรกรรม",
    "created_date": "เวลาที่สร้างคำสั่งซื้อ",
    "date": "เวลาที่ชำระคำสั่งซื้อ",
    "category": "หมวดหมู่",
    "units": "จำนวนชิ้นสุทธิ",
    "net_settlement": "ยอดการชำระเงินทั้งหมด (F)",
    "cogs": "ต้นทุนรวม (G)",
    "profit": "กำไร (H = F - G)",
    "net_sales": "รายได้ทั้งหมด",
    "gross_sales": "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย",
    "gross_sales_before_discount": "ยอดรวมค่าสินค้าก่อนหักส่วนลด",
    "seller_discount": "ส่วนลดจากร้านค้า",
    "refunds": "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย",
    "refunds_before_discount": "ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า",
    "refund_seller_discount": "เงินคืนจากส่วนลดร้านค้า",
    "platform_fees": "ค่าธรรมเนียมทั้งหมด",
    "order_fee": "ค่าธรรมเนียมคำสั่งซื้อ",
    "tiktok_commission": "ค่าคอมมิชชั่น TikTok Shop",
    "commission": "รวมค่าคอมฯ + ค่าธรรมเนียมคำสั่งซื้อ",
    "credit_card_fee": "การผ่อนชำระด้วยบัตรเครดิต",
    "shipping": "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง",
    "affiliate": "ค่าคอมมิชชั่นแอฟฟิลิเอตรวม",
    "growth_fee": "ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า",
    "campaign_service_fee": "ค่าบริการคูปอง/แคมเปญ",
    "infra_and_other_fee": "ค่าธรรมเนียมโครงสร้างพื้นฐาน/อื่นๆ",
    "gmv_max_order_fee": "ค่าโฆษณา/คูปอง GMV Max ในออเดอร์",
    "gmv_ads_deduction": "การชำระเงินด้วย GMV สำหรับโฆษณา TikTok",
    "gmv_ads": "รวมค่าโฆษณา GMV TikTok",
    "other_adjustment": "การปรับยอดอื่นๆ/เงินชดเชย",
    "adjustment": "จำนวนการปรับยอด",
    "customer_payment": "การชำระเงินของลูกค้าสุทธิ",
    "platform_discount": "ส่วนลดจากแพลตฟอร์มสุทธิ",
    "cost_missing": "ยังไม่มีราคาทุน",
    "fee_ratio_%": "สัดส่วนค่าธรรมเนียม %",
}


def company_settlement_view(orders_df: pd.DataFrame) -> pd.DataFrame:
    """จัดเรียงคอลัมน์ตารางรายละเอียดคำสั่งซื้อให้ตรงกับไฟล์ของบริษัท (F=ยอดชำระ, G=ต้นทุนรวม, H=กำไร)"""
    o = ensure_order_columns(orders_df)
    ordered = [
        "order_id",
        "txn_type",
        "created_date",
        "date",
        "net_settlement",
        "cogs",
        "profit",
        "net_sales",
        "gross_sales",
        "gross_sales_before_discount",
        "seller_discount",
        "refunds",
        "platform_fees",
        "order_fee",
        "tiktok_commission",
        "shipping",
        "affiliate",
        "growth_fee",
        "campaign_service_fee",
        "gmv_ads_deduction",
        "adjustment",
        "customer_payment",
        "platform_discount",
        "category",
        "units",
        "cost_missing",
    ]
    present = [c for c in ordered if c in o.columns]
    return o[present].rename(columns=ORDER_COL_TH)


def company_order_lines_view(lines_df: pd.DataFrame) -> pd.DataFrame:
    """จัดเรียงคอลัมน์ชีต Order ให้มี ราคาต่อหน่วย (I) และ มูลค่า (J) ถัดจาก Product Name เหมือนไฟล์บริษัท"""
    if lines_df is None or lines_df.empty:
        return pd.DataFrame()
    preferred = [
        "Order ID",
        "Order Status",
        "Order Substatus",
        "Cancelation/Return Type",
        "SKU ID",
        "Seller SKU",
        "Product Name",
        "ราคาต่อหน่วย",
        "มูลค่า",
        "Variation",
        "Quantity",
        "Sku Quantity of return",
        "net_qty",
        "SKU Unit Original Price",
        "SKU Subtotal Before Discount",
        "SKU Platform Discount",
        "SKU Seller Discount",
        "SKU Subtotal After Discount",
        "Order Amount",
        "Order Refund Amount",
        "Created Time",
        "Paid Time",
        "Product Category",
    ]
    cols = [c for c in preferred if c in lines_df.columns]
    return lines_df[cols].rename(columns={"net_qty": "จำนวนขายสุทธิ"})


def summary_table(s: Summary) -> pd.DataFrame:
    rows: list[tuple[str, float]] = []
    if s.gross_sales_before_discount > 0:
        rows.append(("ยอดรวมค่าสินค้าก่อนหักส่วนลด", s.gross_sales_before_discount))
        rows.append(("หัก ส่วนลดจากร้านค้า", s.seller_discount))
    rows.extend(
        [
            ("ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย", s.gross_sales),
            ("ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย", s.refunds),
            ("รายได้ทั้งหมด (ยอดขายสุทธิ)", s.net_sales),
            ("หัก ค่าธรรมเนียมทั้งหมด (TikTok Shop)", -s.platform_fees),
        ]
    )
    if s.gmv_ads_settlement > 0:
        rows.append(("หัก การชำระเงินด้วย GMV สำหรับโฆษณา TikTok / โปรโมท", -s.gmv_ads_settlement))
    if abs(s.other_adjustment) > 0:
        rows.append(("บวก/หัก การปรับยอดอื่นๆ และเงินชดเชย", s.other_adjustment))

    rows.extend(
        [
            ("ยอดการชำระเงินทั้งหมด (คอลัมน์ F — เงินรับสุทธิจาก TikTok)", s.net_settlement),
            ("หัก ต้นทุนสินค้ารวม (คอลัมน์ G — ราคาทุน SKU × จำนวนสุทธิ)", -s.cogs),
        ]
    )
    if abs(s.order_only_profit - s.settlement_profit) >= 1:
        rows.append(("กำไรเฉพาะคำสั่งซื้อ (ก่อนหักโฆษณา GMV / ปรับยอด)", s.order_only_profit))
    rows.append(("กำไรสุทธิจากยอดโอน (F − G หลังหักโฆษณา GMV แล้ว)", s.settlement_profit))
    if s.ads > 0:
        rows.append(("หัก ค่าโฆษณาเพิ่มเติมจากชีต Ads ภายนอก", -s.ads))
        rows.append(("กำไรจากการขาย (หลังหักค่าโฆษณาภายนอก)", s.rough_profit))

    rows.extend(
        [
            (f"หัก ค่าคอมมิชชั่นคนขาย ({s.comm_pct:.1f}%)", -s.sales_commission),
            ("หัก ค่าใช้จ่ายโรงงานรายเดือน (ค่าแรง+ค่าน้ำ+ค่าไฟ+อื่นๆ)", -s.fixed_costs),
            ("กำไรสุทธิสุดท้ายประจำเดือน", s.net_profit),
            ("จำนวนคำสั่งซื้อทั้งหมด (ออเดอร์)", float(s.orders)),
            ("จำนวนคำสั่งซื้อที่ขายขาดทุน (เทียบราคาทุน SKU)", float(s.losing_orders_count)),
            ("จำนวนชิ้นที่ขายสุทธิ", float(s.units)),
        ]
    )
    return pd.DataFrame(rows, columns=["รายการ", "จำนวนเงิน / ค่า"])


def format_thai_cost_filename(period_label: str) -> str:
    """แปลงชื่องวดเป็นชื่อไฟล์ต้นทุนมาตรฐานของบริษัท เช่น '2026-09' -> 'ต้นทุน2569-09.xlsx'"""
    clean = str(period_label).strip()
    if not clean:
        return "ต้นทุน.xlsx"

    # ตัดช่องว่างและสัญลักษณ์แปลกปลอม
    m = re.search(r"(\d{4})[-/](\d{1,2})", clean)
    if m:
        yr, mo = int(m.group(1)), int(m.group(2))
        if yr < 2500:
            yr += 543
        extra = ""
        if "ดีไวน์" in clean:
            extra = "ดีไวน์"
        return f"ต้นทุน{extra}{yr}-{mo:02d}.xlsx"

    clean_slug = re.sub(r'[\/:*?"<>| ]', "_", clean)
    return f"ต้นทุน_{clean_slug}.xlsx"


def _split_order_sheets_by_month(df: pd.DataFrame, default_name: str) -> list[tuple[str, pd.DataFrame]]:
    """แบ่งแถวคำสั่งซื้อเป็นชีตละเดือนตาม Created Time (ไฟล์ Order ของ TikTok ใช้รูปแบบวันที่ dd/mm/yyyy)

    ถ้ามีเดือนเดียว หรืออ่านวันที่ไม่ได้ จะคืนชีตเดียวชื่อ default_name เหมือนเดิม
    """
    if df is None or df.empty or "Created Time" not in df.columns or "Order ID" not in df.columns:
        return [(default_name, df)]
    ids = df["Order ID"].astype(str).str.strip()
    body = df[ids.str.fullmatch(r"\d+")].drop_duplicates()
    months = pd.to_datetime(body["Created Time"], errors="coerce", format="mixed", dayfirst=True).dt.to_period("M")
    valid = sorted(months.dropna().unique(), reverse=True)
    if len(valid) <= 1:
        return [(default_name, df)]
    # บริษัทต้องการ Order แค่ 2 เดือนติดกันเสมอ (เช่น 8 กับ 9, 9 กับ 10, 10 กับ 11)
    if len(valid) > 2:
        valid = valid[:2]
    months = months.fillna(valid[0])
    same_month_num = len({m.month for m in valid}) < len(valid)
    out: list[tuple[str, pd.DataFrame]] = []
    for m in valid:
        name = f"Order{m.year}-{m.month:02d}" if same_month_num else f"Order{m.month}"
        out.append((name, body[months == m].reset_index(drop=True)))
    return out


def build_company_cost_master_excel(
    res,
    sku_master: pd.DataFrame,
    period_label: str = "",
    order_sheet_name: str | None = None,
) -> bytes:
    """สร้างไฟล์ Excel ต้นทุนรวมฉบับสมบูรณ์ (ต้นทุน(ปี-เดือน).xlsx)
    โครงสร้างชีตตรงกับไฟล์ของบริษัท 100%:
    1. รายละเอียดคำสั่งซื้อ (แทรก Col F: ยอดชำระ, Col G: ต้นทุนรวม, Col H: กำไร)
    2. SKU (ตารางราคาทุนสินค้า)
    3. Order (แทรก Col I: ราคาต่อหน่วย, Col J: มูลค่า)
    4. รายงาน (TikTok Report)
    5. บันทึกการถอน (Withdrawals)
    6. คำอธิบายค่าธรรมเนียม (Fee Descriptions)
    7. ads (ถ้ามี)
    """
    buf = BytesIO()

    # 1. เตรียมชีต 'รายละเอียดคำสั่งซื้อ'
    raw_s = getattr(res, "raw_settlement", None)
    if raw_s is not None and not raw_s.empty:
        settle_df = raw_s.copy()
        # หา column ID
        id_col = "หมายเลขคำสั่งซื้อ/การปรับ" if "หมายเลขคำสั่งซื้อ/การปรับ" in settle_df.columns else settle_df.columns[0]
        s_oids = settle_df[id_col].astype(str).str.strip()

        cogs_map = dict(zip(res.orders["order_id"].astype(str).str.strip(), res.orders["cogs"]))
        profit_map = dict(zip(res.orders["order_id"].astype(str).str.strip(), res.orders["profit"]))

        f_col_name = "ยอดการชำระเงินทั้งหมด" if "ยอดการชำระเงินทั้งหมด" in settle_df.columns else None
        if f_col_name:
            f_idx = settle_df.columns.get_loc(f_col_name)
        else:
            f_idx = min(5, len(settle_df.columns) - 1)

        part1 = settle_df.iloc[:, : f_idx + 1].copy()
        part2 = settle_df.iloc[:, f_idx + 1 :].copy()

        # ลบคอลัมน์ ต้นทุนรวม และ กำไร ใน part2 หากมีติดมาเดิม
        part2 = part2.drop(columns=[c for c in ("ต้นทุนรวม", "กำไร") if c in part2.columns], errors="ignore")

        part1["ต้นทุนรวม"] = s_oids.map(cogs_map).fillna(0.0)
        part1["กำไร"] = s_oids.map(profit_map).fillna(0.0)

        final_settle = pd.concat([part1, part2], axis=1)
    else:
        final_settle = company_settlement_view(res.orders)

    # 2. เตรียมชีต 'Order' (เช่น Order9 หรือ OrderSKUList)
    explicit_order_sheet = bool(order_sheet_name)
    if not order_sheet_name:
        m = re.search(r"[-/](\d{1,2})", str(period_label))
        if m:
            order_sheet_name = f"Order{int(m.group(1))}"
        else:
            order_sheet_name = "OrderSKUList"

    raw_o = getattr(res, "raw_orders", None)
    if raw_o is not None and not raw_o.empty:
        o_df = raw_o.copy()
        pname_col = "Product Name" if "Product Name" in o_df.columns else None
        if pname_col:
            p_idx = o_df.columns.get_loc(pname_col)
        else:
            p_idx = min(7, len(o_df.columns) - 1)

        sku_col = "Seller SKU" if "Seller SKU" in o_df.columns else "SKU ID"
        qty_col = "Quantity" if "Quantity" in o_df.columns else None

        sku_cost_map = dict(zip(sku_master["sku"].astype(str).str.strip(), sku_master["unit_cost"]))
        seller_skus = o_df[sku_col].astype(str).str.strip() if sku_col in o_df.columns else pd.Series(0.0, index=o_df.index)
        unit_costs = seller_skus.map(sku_cost_map).fillna(0.0)

        if qty_col and qty_col in o_df.columns:
            quantities = pd.to_numeric(o_df[qty_col], errors="coerce").fillna(0.0)
        else:
            quantities = pd.Series(1.0, index=o_df.index)

        item_cogs = unit_costs * quantities

        p1_o = o_df.iloc[:, : p_idx + 1].copy()
        p2_o = o_df.iloc[:, p_idx + 1 :].copy()
        p2_o = p2_o.drop(columns=[c for c in ("ราคาต่อหน่วย", "มูลค่า", "ต้นทุนต่อคำสั่งซื้อ") if c in p2_o.columns], errors="ignore")

        p1_o["ราคาต่อหน่วย"] = unit_costs
        p1_o["มูลค่า"] = item_cogs
        final_orders = pd.concat([p1_o, p2_o], axis=1)
    else:
        final_orders = company_order_lines_view(res.order_lines)

    # 3. เตรียมชีต 'SKU'
    sku_cols = ["sku", "name", "category", "unit_cost", "retail_price", "promo_price", "list_price"]
    sku_th = {
        "sku": "รหัส",
        "name": "ชื่อ",
        "category": "หมวดหมู่",
        "unit_cost": "ราคาทุน",
        "retail_price": "ราคาปลีก",
        "promo_price": "ราคาโปร",
        "list_price": "ราคาตั้งขาย",
    }
    present_sku_cols = [c for c in sku_cols if c in sku_master.columns]
    final_sku = sku_master[present_sku_cols].rename(columns=sku_th)

    # เขียนลงไฟล์ Excel ด้วย xlsxwriter
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        book = xw.book
        money_fmt = book.add_format({"num_format": "#,##0.00"})
        int_fmt = book.add_format({"num_format": "#,##0"})
        header_fmt = book.add_format({
            "bold": True,
            "bg_color": "#E0E7FF",
            "font_color": "#1E3A8A",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })

        def _write_sheet(df: pd.DataFrame, sheet_title: str):
            if df is None or df.empty:
                return
            clean_df = df.copy()
            for col in clean_df.select_dtypes(include=["datetimetz", "datetime"]).columns:
                clean_df[col] = clean_df[col].dt.tz_localize(None) if hasattr(clean_df[col].dt, "tz") and clean_df[col].dt.tz else clean_df[col]
            s_name = re.sub(r"[:\\/?*\[\]]", "-", sheet_title)[:31]
            clean_df.to_excel(xw, sheet_name=s_name, index=False)
            ws = xw.sheets[s_name]
            for col_idx, col_name in enumerate(clean_df.columns):
                ws.write(0, col_idx, str(col_name), header_fmt)
                col_data = clean_df[col_name]
                width = min(max(len(str(col_name)), 12) + 3, 40)
                fmt = None
                if pd.api.types.is_float_dtype(col_data):
                    fmt = money_fmt
                elif pd.api.types.is_integer_dtype(col_data):
                    fmt = int_fmt
                ws.set_column(col_idx, col_idx, width, fmt)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(clean_df), len(clean_df.columns) - 1)

        # ชีต 1: รายละเอียดคำสั่งซื้อ
        _write_sheet(final_settle, "รายละเอียดคำสั่งซื้อ")

        # ชีต 2: SKU
        _write_sheet(final_sku, "SKU")

        # ชีต 3: Order — แยกชีตตามเดือนที่สั่งซื้อ (เช่น Order9, Order8) เมื่อมีคำสั่งซื้อหลายเดือน
        if explicit_order_sheet:
            order_sheets = [(order_sheet_name, final_orders)]
        else:
            order_sheets = _split_order_sheets_by_month(final_orders, order_sheet_name)
        for o_name, o_part in order_sheets:
            _write_sheet(o_part, o_name)

        # ชีต 4: รายงาน
        extra_sheets = getattr(res, "extra_sheets", {}) or {}
        if "รายงาน" in extra_sheets and not extra_sheets["รายงาน"].empty:
            rep_df = extra_sheets["รายงาน"]
            s_name = "รายงาน"
            rep_df.to_excel(xw, sheet_name=s_name, index=False, header=False)
        else:
            rep_table = tiktok_report_table(res) if "tiktok_report_table" in globals() else pd.DataFrame()
            if not rep_table.empty:
                _write_sheet(rep_table, "รายงาน")

        # ชีต 5: บันทึกการถอน
        if res.withdrawals is not None and not res.withdrawals.empty:
            _write_sheet(res.withdrawals, "บันทึกการถอน")

        # ชีต 6: คำอธิบายค่าธรรมเนียม
        if "คำอธิบายค่าธรรมเนียม" in extra_sheets and not extra_sheets["คำอธิบายค่าธรรมเนียม"].empty:
            fee_df = extra_sheets["คำอธิบายค่าธรรมเนียม"]
            fee_df.to_excel(xw, sheet_name="คำอธิบายค่าธรรมเนียม", index=False, header=False)
        else:
            fee_ref_df = pd.DataFrame(list(FEE_DESCRIPTIONS.items()), columns=["รายการค่าธรรมเนียม", "คำอธิบาย"])
            _write_sheet(fee_ref_df, "คำอธิบายค่าธรรมเนียม")

        # ชีต 7: ads
        if res.ads is not None and not res.ads.empty:
            _write_sheet(res.ads, "ads")

    return buf.getvalue()


def to_excel(summary: Summary, sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        book = xw.book
        money = book.add_format({"num_format": "#,##0.00"})
        bold = book.add_format({"bold": True, "bg_color": "#DBEAFE", "border": 1})

        all_sheets = {"สรุปงบกำไรขาดทุน": summary_table(summary), **sheets}
        for name, df in all_sheets.items():
            if df is None or df.empty:
                continue
            out = df.rename(columns=ORDER_COL_TH).copy()
            for col in out.select_dtypes(include=["datetimetz", "datetime"]).columns:
                out[col] = out[col].dt.tz_localize(None) if hasattr(out[col].dt, "tz") and out[col].dt.tz else out[col]
            sheet = re.sub(r"[:\\/?*\[\]]", "-", name)[:31]
            out.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            for i, col in enumerate(out.columns):
                ws.write(0, i, col, bold)
                width = min(max(len(str(col)), 12) + 4, 48)
                fmt = money if pd.api.types.is_float_dtype(out[col]) else None
                ws.set_column(i, i, width, fmt)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(out), len(out.columns) - 1)
    return buf.getvalue()


def to_html_report(summary: Summary, period: str, categories: pd.DataFrame, top_sku: pd.DataFrame) -> str:
    """รายงานสรุปผู้บริหาร 1 หน้า (เปิดในเบราว์เซอร์แล้ว Print → Save as PDF)"""

    def fmt(v: float) -> str:
        return f"{v:,.2f}"

    def table(df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return "<p><i>ไม่มีข้อมูล</i></p>"
        return df.to_html(index=False, float_format=lambda x: f"{x:,.2f}", border=0, classes="t")

    s = summary
    bep = fmt(s.break_even_sales) if s.break_even_sales is not None else "คำนวณไม่ได้ (กำไรส่วนเกินติดลบ)"
    return f"""<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">
<title>รายงานสรุปต้นทุนและกำไร {period}</title>
<style>
 @page {{ size: A4; margin: 14mm; }}
 body {{ font-family: "Sarabun","Thonburi",sans-serif; color:#1e293b; font-size:11pt; }}
 h1 {{ color:#1e3a8a; font-size:17pt; margin:0; }} h2 {{ color:#1e40af; font-size:13pt; border-left:4px solid #2563eb; padding-left:8px; }}
 .kpis {{ display:flex; gap:10px; margin:14px 0; }}
 .kpi {{ flex:1; border:1px solid #cbd5e1; border-radius:8px; padding:8px 10px; }}
 .kpi b {{ display:block; font-size:14pt; }} .neg {{ color:#b91c1c; }} .pos {{ color:#15803d; }}
 table.t {{ width:100%; border-collapse:collapse; font-size:9.5pt; }}
 table.t th, table.t td {{ border:1px solid #cbd5e1; padding:4px 6px; text-align:right; }}
 table.t th {{ background:#f1f5f9; }} table.t td:first-child, table.t th:first-child {{ text-align:left; }}
 .muted {{ color:#64748b; font-size:9pt; }}
</style></head><body>
<h1>รายงานสรุปต้นทุนและกำไร</h1>
<div class="muted">บริษัท มาตัง คอสเมติก จำกัด · งวด {period} · สร้างเมื่อ {datetime.now():%d/%m/%Y %H:%M}</div>
<div class="kpis">
 <div class="kpi">รายได้ทั้งหมด<b>{fmt(s.net_sales)}</b></div>
 <div class="kpi">ยอดการชำระเงินทั้งหมด (F)<b>{fmt(s.net_settlement)}</b></div>
 <div class="kpi">ต้นทุนสินค้า SKU (G)<b>{fmt(s.cogs)}</b></div>
 <div class="kpi">กำไรสุทธิสุดท้าย<b class="{'pos' if s.net_profit >= 0 else 'neg'}">{fmt(s.net_profit)}</b></div>
</div>
<h2>งบกำไรขาดทุนตามโครงสร้าง TikTok Shop และบริษัท</h2>{table(summary_table(s))}
<p>ยอดขาย ณ จุดคุ้มทุน: <b>{bep}</b> บาท</p>
<h2>กำไรตามหมวดหมู่สินค้า</h2>{table(categories)}
<h2>สินค้าขายดี 10 อันดับ</h2>{table(top_sku)}
</body></html>"""
