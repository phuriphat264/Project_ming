"""ส่งออกรายงานเป็น Excel (.xlsx) และ HTML/PDF ตามโครงสร้างคอลัมน์มาตรฐานของ TikTok Shop และบริษัท"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re

import pandas as pd

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
