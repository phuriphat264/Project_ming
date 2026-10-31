"""เติมข้อมูลจำลองที่สมบูรณ์ลงในไฟล์ Excel (.xlsx) ทุกไฟล์ใน /Users/phuriphat/Project_ming/
และล้างข้อมูลจำลองเดิมในฐานข้อมูล (SQLite + Parquet Snapshots) เพื่อให้ผู้ใช้ทดสอบอัปโหลดเริ่มใหม่ได้ทันที
"""
from __future__ import annotations

from pathlib import Path
import random
import sys

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path("/Users/phuriphat/Project_ming")
APP_DIR = ROOT / "cost_profit_system"
sys.path.insert(0, str(APP_DIR))

from core import db
from core.loader import load_workbook
from core.pipeline import combine, run_pipeline


def infer_category(name: str) -> str:
    n = str(name)
    if "กันแดด" in n:
        return "ผลิตภัณฑ์กันแดด"
    if any(k in n for k in ("เซรั่ม", "โดส", "ไฮยา", "บูสเตอร์", "แอมพูล")):
        return "เซรั่มและบูสเตอร์"
    if any(k in n for k in ("สบู่", "คลีนซิ่ง", "โฟม")):
        return "ผลิตภัณฑ์ทำความสะอาดผิว"
    if "ออยล์" in n:
        return "ออยล์บำรุงผิว"
    if any(k in n for k in ("เซ็ต", "+", "แถม", "คู่")):
        return "ชุดเซ็ตโปรโมชั่น"
    return "ครีมบำรุงผิวและโลชั่น"


def build_master_sku() -> pd.DataFrame:
    """รวมรหัสสินค้าจากฐานข้อมูลเดิมและชีต SKU ในไฟล์เดือน 06 และออเดอร์เดือน 09"""
    skus_db = db.get_skus()
    w6 = load_workbook(str(ROOT / "ต้นทุนดีไวน์2569-06.xlsx"))
    w9 = load_workbook(str(ROOT / "ต้นทุนดีไวน์2569-09.xlsx"))
    w9_big = load_workbook(str(ROOT / "ต้นทุน2569-09.xlsx"))

    rows: dict[str, dict] = {}

    if not w6.sku.empty:
        for _, r in w6.sku.iterrows():
            code = str(r.get("รหัส", "")).strip()
            if not code or code.lower() == "nan":
                continue
            name = str(r.get("ชื่อ", "")).strip()
            cost = float(pd.to_numeric(r.get("ราคาทุน", 0), errors="coerce") or 0)
            retail = float(pd.to_numeric(r.get("ราคาปลีก", 0), errors="coerce") or 0)
            promo = float(pd.to_numeric(r.get("ราคาโปร", 0), errors="coerce") or 0)
            list_p = float(pd.to_numeric(r.get("ราคาตั้งขาย", 0), errors="coerce") or 0)
            rows[code] = {
                "รหัส": code,
                "ชื่อ": name,
                "หมวดหมู่": infer_category(name),
                "ราคาทุน": cost if cost > 0 else 110.0,
                "ราคาปลีก": retail if retail > 0 else 390.0,
                "ราคาโปร": promo if promo > 0 else 290.0,
                "ราคาตั้งขาย": list_p if list_p > 0 else 590.0,
            }

    if not skus_db.empty:
        for _, r in skus_db.iterrows():
            code = str(r["sku"]).strip()
            if not code:
                continue
            name = str(r.get("name", "")).strip() or rows.get(code, {}).get("ชื่อ", code)
            cat = str(r.get("category", "")).strip() or infer_category(name)
            cost = float(r.get("unit_cost", 0) or 0)
            retail = float(r.get("retail_price", 0) or 0)
            promo = float(r.get("promo_price", 0) or 0)
            prev = rows.get(code, {})
            rows[code] = {
                "รหัส": code,
                "ชื่อ": name,
                "หมวดหมู่": cat if cat else infer_category(name),
                "ราคาทุน": cost if cost > 0 else prev.get("ราคาทุน", 115.0),
                "ราคาปลีก": retail if retail > 0 else prev.get("ราคาปลีก", 390.0),
                "ราคาโปร": promo if promo > 0 else prev.get("ราคาโปร", 290.0),
                "ราคาตั้งขาย": prev.get("ราคาตั้งขาย", max(retail * 1.2, 490.0)),
            }

    for odf in (w9.orders, w9_big.orders):
        if odf.empty:
            continue
        grouped = (
            odf.groupby("Seller SKU")
            .agg(
                name=("Product Name", "first"),
                orig_price=("SKU Unit Original Price", "median"),
                after_price=("SKU Subtotal After Discount", "median"),
            )
            .reset_index()
        )
        for _, r in grouped.iterrows():
            code = str(r["Seller SKU"]).strip()
            if not code or code.lower() == "nan":
                continue
            if code not in rows:
                name = str(r["name"]).strip()
                promo = round(float(r["after_price"] or 290.0), 2)
                retail = round(float(r["orig_price"] or max(promo * 1.35, 390.0)), 2)
                cost = round(max(65.0, promo * 0.36), 2)
                rows[code] = {
                    "รหัส": code,
                    "ชื่อ": name,
                    "หมวดหมู่": infer_category(name),
                    "ราคาทุน": cost,
                    "ราคาปลีก": retail,
                    "ราคาโปร": promo,
                    "ราคาตั้งขาย": round(retail * 1.2, 2),
                }

    df = pd.DataFrame(list(rows.values())).sort_values("รหัส").reset_index(drop=True)
    return df


def make_ads_df(year_month: str, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    dates = pd.date_range(f"{year_month}-01", periods=28, freq="D")
    records = []
    campaigns = [
        ("GMV Max โปรโมทสินค้าขายดี", "CMP-GMV-001"),
        ("Live Shopping Boost รอบค่ำ", "CMP-LIVE-002"),
        ("Video Ads รีวิวครีมบำรุงผิว", "CMP-VID-003"),
    ]
    for d in dates:
        cname, cid = rng.choice(campaigns)
        cash = round(rng.uniform(1200.0, 4800.0), 2)
        credit = round(rng.choice([0.0, 0.0, 300.0, 500.0]), 2)
        total = round(cash + credit, 2)
        records.append(
            {
                "วันที่": d.strftime("%Y-%m-%d"),
                "ชื่อแคมเปญ": f"{cname} ({year_month})",
                "รหัสแคมเปญ": cid,
                "ค่าใช้จ่ายที่เป็นเงินสด": cash,
                "ค่าใช้จ่ายเครดิต": 0.0,
                "ค่าใช้จ่ายเครดิตโฆษณา": credit,
                "จำนวนรวม": total,
                "สกุลเงิน": "THB",
                "ประเภท": "การหักเงินอัตโนมัติ",
            }
        )
    return pd.DataFrame(records)


def make_synthetic_month_data(year_month: str, master_sku: pd.DataFrame, n_orders: int, seed: int):
    """สร้างทั้งชีต รายละเอียดคำสั่งซื้อ และ Order ที่จับคู่ Order ID กันครบ 100%"""
    rng = np.random.default_rng(seed)
    sku_records = master_sku.to_dict("records")
    days_in_month = pd.Period(year_month, freq="M").days_in_month

    base_order_id = 580000000000000000 + seed * 1000000000
    settlement_rows = []
    order_rows = []

    for i in range(n_orders):
        oid = str(base_order_id + i)
        day = int(rng.integers(1, days_in_month + 1))
        date_str = f"{year_month.replace('-', '/')}/{day:02d}"
        dt_order_str = f"{day:02d}/{year_month.split('-')[1]}/{year_month.split('-')[0]} 14:20:00"

        item = sku_records[int(rng.integers(0, len(sku_records)))]
        qty = int(rng.choice([1, 1, 1, 1, 2, 2, 3]))
        orig_unit = float(item["ราคาปลีก"])
        promo_unit = float(item["ราคาโปร"])
        if promo_unit <= 0:
            promo_unit = orig_unit

        before_disc = round(orig_unit * qty, 2)
        after_disc = round(promo_unit * qty, 2)
        seller_disc = round(max(0.0, before_disc - after_disc), 2)

        is_refund = bool(rng.random() < 0.05)
        status = "ยกเลิกแล้ว" if is_refund else "เสร็จสมบูรณ์"
        ret_qty = qty if is_refund else 0
        refund_amt = -after_disc if is_refund else 0.0

        # ค่าธรรมเนียม TikTok Shop
        order_fee = round(-after_disc * 0.032, 2) if not is_refund else 0.0
        comm_fee = round(-after_disc * 0.064, 2) if not is_refund else 0.0
        aff_fee = round(-after_disc * float(rng.choice([0.0, 0.05, 0.08, 0.10])), 2) if not is_refund else 0.0
        ship_fee = round(float(rng.choice([0.0, 0.0, 0.0, -38.0, -45.0])), 2)
        total_fee = round(order_fee + comm_fee + aff_fee + ship_fee, 2)

        net_sales_row = round(after_disc + refund_amt, 2)
        net_settlement = round(net_sales_row + total_fee, 2)

        settlement_rows.append(
            {
                "หมายเลขคำสั่งซื้อ/การปรับ": oid,
                "ประเภทธุรกรรม": "คำสั่งซื้อ",
                "เวลาที่สร้างคำสั่งซื้อ": date_str,
                "เวลาที่ชำระคำสั่งซื้อ": date_str,
                "สกุลเงิน": "THB",
                "จำนวนเงินที่ชำระทั้งหมด": net_settlement,
                "รายได้รวม": net_sales_row,
                "รายได้ทั้งหมด": net_sales_row,
                "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย": after_disc,
                "ยอดรวมค่าสินค้าก่อนหักส่วนลด": before_disc,
                "ส่วนลดจากร้านค้า": -seller_disc,
                "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย": refund_amt,
                "ค่าธรรมเนียมทั้งหมด": total_fee,
                "ค่าธรรมเนียมคำสั่งซื้อ": order_fee,
                "ค่าคอมมิชชั่น TikTok Shop": comm_fee,
                "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง": ship_fee,
                "ค่าคอมมิชชั่นแอฟฟิลิเอต": aff_fee,
                "ค่าโฆษณา GMV Max": 0.0,
                "จำนวนการปรับยอด": 0.0,
            }
        )

        order_rows.append(
            {
                "Order ID": oid,
                "Order Status": status,
                "Order Substatus": status,
                "Cancelation/Return Type": "Cancel" if is_refund else "",
                "Normal or Pre-order": "Normal",
                "SKU ID": f"173{int(rng.integers(100000000000000, 999999999999999))}",
                "Seller SKU": item["รหัส"],
                "Product Name": item["ชื่อ"],
                "Variation": "มาตรฐาน",
                "Quantity": qty,
                "Sku Quantity of return": ret_qty,
                "SKU Unit Original Price": orig_unit,
                "SKU Subtotal Before Discount": before_disc,
                "SKU Platform Discount": 0.0,
                "SKU Seller Discount": seller_disc,
                "SKU Subtotal After Discount": after_disc,
                "Shipping Fee After Discount": 0.0,
                "Original Shipping Fee": 38.0,
                "Order Amount": after_disc,
                "Order Refund Amount": abs(refund_amt),
                "Created Time": dt_order_str,
                "Product Category": item["หมวดหมู่"],
            }
        )

    return pd.DataFrame(settlement_rows), pd.DataFrame(order_rows)


def build_orders_for_existing_settlement(settlement_df: pd.DataFrame, master_sku: pd.DataFrame, seed: int) -> pd.DataFrame:
    """สร้างชีต Order ให้ตรงกับ Order ID ที่มีอยู่ในชีต รายละเอียดคำสั่งซื้อ (เช่น ไฟล์ 2569-07-1)"""
    rng = np.random.default_rng(seed)
    sku_records = master_sku.to_dict("records")
    order_rows = []

    txns = settlement_df[settlement_df["ประเภทธุรกรรม"] == "คำสั่งซื้อ"].copy()
    for idx, r in txns.iterrows():
        oid = str(r["หมายเลขคำสั่งซื้อ/การปรับ"]).strip()
        if not oid.isdigit():
            continue
        item = sku_records[int(rng.integers(0, len(sku_records)))]
        after_disc = float(r.get("ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย", 0) or 0)
        before_disc = float(r.get("ยอดรวมค่าสินค้าก่อนหักส่วนลด", 0) or after_disc)
        seller_disc = abs(float(r.get("ส่วนลดจากร้านค้า", 0) or 0))
        refund_amt = abs(float(r.get("ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย", 0) or 0))

        promo_unit = max(float(item["ราคาโปร"] or 250.0), 50.0)
        qty = max(1, int(round(after_disc / promo_unit))) if after_disc > 0 else 1
        orig_unit = round(before_disc / qty, 2) if before_disc > 0 else float(item["ราคาปลีก"] or 390.0)
        is_refund = refund_amt > 0 and after_disc <= refund_amt

        dt_val = pd.to_datetime(r.get("เวลาที่สร้างคำสั่งซื้อ"), errors="coerce")
        dt_str = dt_val.strftime("%d/%m/%Y 12:00:00") if pd.notna(dt_val) else "15/07/2026 12:00:00"

        order_rows.append(
            {
                "Order ID": oid,
                "Order Status": "ยกเลิกแล้ว" if is_refund else "เสร็จสมบูรณ์",
                "Order Substatus": "ยกเลิกแล้ว" if is_refund else "เสร็จสมบูรณ์",
                "Cancelation/Return Type": "Return/Refund" if is_refund else "",
                "Normal or Pre-order": "Normal",
                "SKU ID": f"173000{idx:010d}",
                "Seller SKU": item["รหัส"],
                "Product Name": item["ชื่อ"],
                "Variation": "1 ชิ้น",
                "Quantity": qty,
                "Sku Quantity of return": qty if is_refund else 0,
                "SKU Unit Original Price": orig_unit,
                "SKU Subtotal Before Discount": before_disc if before_disc > 0 else round(orig_unit * qty, 2),
                "SKU Platform Discount": 0.0,
                "SKU Seller Discount": seller_disc,
                "SKU Subtotal After Discount": after_disc if after_disc > 0 else round(promo_unit * qty, 2),
                "Shipping Fee After Discount": 0.0,
                "Original Shipping Fee": 38.0,
                "Order Amount": after_disc,
                "Order Refund Amount": refund_amt,
                "Created Time": dt_str,
                "Product Category": item["หมวดหมู่"],
            }
        )
    return pd.DataFrame(order_rows)


def build_settlement_for_existing_orders(orders_df: pd.DataFrame, year_month: str, seed: int) -> pd.DataFrame:
    """สร้างชีต รายละเอียดคำสั่งซื้อ ให้ตรงกับ Order ID ที่มีอยู่ในชีต Order9 (เช่น ไฟล์ ต้นทุนดีไวน์2569-09.xlsx)"""
    rng = np.random.default_rng(seed)
    grouped = (
        orders_df.groupby("Order ID", as_index=False)
        .agg(
            status=("Order Status", "first"),
            before_disc=("SKU Subtotal Before Discount", "sum"),
            seller_disc=("SKU Seller Discount", "sum"),
            after_disc=("SKU Subtotal After Discount", "sum"),
            ret_qty=("Sku Quantity of return", "sum"),
            qty=("Quantity", "sum"),
            created=("Created Time", "first"),
        )
    )
    days_in_month = pd.Period(year_month, freq="M").days_in_month
    settlement_rows = []
    for _, r in grouped.iterrows():
        oid = str(r["Order ID"]).strip()
        is_cancel = str(r["status"]).strip() == "ยกเลิกแล้ว" or (r["ret_qty"] >= r["qty"] and r["qty"] > 0)
        before_d = round(float(r["before_disc"] or 0), 2)
        after_d = round(float(r["after_disc"] or 0), 2)
        seller_d = round(float(r["seller_disc"] or max(0.0, before_d - after_d)), 2)

        dt_val = pd.to_datetime(r["created"], errors="coerce")
        if pd.notna(dt_val):
            date_str = dt_val.strftime("%Y/%m/%d")
        else:
            day = int(rng.integers(1, days_in_month + 1))
            date_str = f"{year_month.replace('-', '/')}/{day:02d}"

        if is_cancel:
            refund_amt = -after_d
            order_fee = 0.0
            comm_fee = 0.0
            aff_fee = 0.0
            ship_fee = round(float(rng.choice([0.0, 0.0, -38.0])), 2)
        else:
            refund_amt = 0.0
            order_fee = round(-after_d * 0.032, 2)
            comm_fee = round(-after_d * 0.064, 2)
            aff_fee = round(-after_d * float(rng.choice([0.0, 0.05, 0.08])), 2)
            ship_fee = round(float(rng.choice([0.0, 0.0, 0.0, -38.0])), 2)

        total_fee = round(order_fee + comm_fee + aff_fee + ship_fee, 2)
        net_sales_row = round(after_d + refund_amt, 2)
        net_settlement = round(net_sales_row + total_fee, 2)

        settlement_rows.append(
            {
                "หมายเลขคำสั่งซื้อ/การปรับ": oid,
                "ประเภทธุรกรรม": "คำสั่งซื้อ",
                "เวลาที่สร้างคำสั่งซื้อ": date_str,
                "เวลาที่ชำระคำสั่งซื้อ": date_str,
                "สกุลเงิน": "THB",
                "จำนวนเงินที่ชำระทั้งหมด": net_settlement,
                "รายได้รวม": net_sales_row,
                "รายได้ทั้งหมด": net_sales_row,
                "ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย": after_d,
                "ยอดรวมค่าสินค้าก่อนหักส่วนลด": before_d,
                "ส่วนลดจากร้านค้า": -seller_d,
                "ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย": refund_amt,
                "ค่าธรรมเนียมทั้งหมด": total_fee,
                "ค่าธรรมเนียมคำสั่งซื้อ": order_fee,
                "ค่าคอมมิชชั่น TikTok Shop": comm_fee,
                "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง": ship_fee,
                "ค่าคอมมิชชั่นแอฟฟิลิเอต": aff_fee,
                "ค่าโฆษณา GMV Max": 0.0,
                "จำนวนการปรับยอด": 0.0,
            }
        )
    return pd.DataFrame(settlement_rows)


def write_workbook_clean(
    path: Path,
    sku_df: pd.DataFrame,
    settlement_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    ads_df: pd.DataFrame,
    order_sheet_name: str = "Order",
    ads_sheet_name: str = "ads",
) -> None:
    """บันทึกไฟล์ .xlsx ให้มีครบทุกชีตสำคัญ (SKU, รายละเอียดคำสั่งซื้อ, Order, ads) พร้อมใช้งานทันที"""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sku_df.to_excel(writer, sheet_name="SKU", index=False)
        settlement_df.to_excel(writer, sheet_name="รายละเอียดคำสั่งซื้อ", index=False)
        orders_df.to_excel(writer, sheet_name=order_sheet_name, index=False)
        ads_df.to_excel(writer, sheet_name=ads_sheet_name, index=False)


def update_large_2569_09(path: Path, master_sku: pd.DataFrame) -> None:
    """สำหรับไฟล์ใหญ่ ต้นทุน2569-09.xlsx: เติมชีต SKU และแคมเปญโฆษณา และเติมออเดอร์ที่ขาดใน Order9"""
    print("Updating large file:", path.name)
    w = load_workbook(str(path))
    existing_oids = set(w.orders["Order ID"].astype(str).str.strip()) if not w.orders.empty else set()
    missing_settlement = w.settlement[
        (w.settlement["ประเภทธุรกรรม"] == "คำสั่งซื้อ")
        & (~w.settlement["หมายเลขคำสั่งซื้อ/การปรับ"].astype(str).str.strip().isin(existing_oids))
    ]
    extra_orders = build_orders_for_existing_settlement(missing_settlement, master_sku, seed=909)
    ads_df = make_ads_df("2026-09", seed=909)

    wb = openpyxl.load_workbook(path)
    # 1. Replace SKU sheet
    if "SKU" in wb.sheetnames:
        del wb["SKU"]
    ws_sku = wb.create_sheet("SKU", 1)
    ws_sku.append(list(master_sku.columns))
    for row in master_sku.itertuples(index=False, name=None):
        ws_sku.append(list(row))

    # 2. Replace Order9 sheet with extra_orders so 100% of orders match
    if "Order9" in wb.sheetnames:
        del wb["Order9"]
    ws_o9 = wb.create_sheet("Order9", 2)
    if not extra_orders.empty:
        ws_o9.append(list(extra_orders.columns))
        for row in extra_orders.itertuples(index=False, name=None):
            ws_o9.append(list(row))

    # 3. Add ads sheet
    if "ads" in wb.sheetnames:
        del wb["ads"]
    ws_ads = wb.create_sheet("ads")
    ws_ads.append(list(ads_df.columns))
    for row in ads_df.itertuples(index=False, name=None):
        ws_ads.append(list(row))

    wb.save(path)
    wb.close()


def main() -> None:
    print("1. Building master SKU table...")
    master_sku = build_master_sku()
    print(f"   Master SKU count: {len(master_sku)} items")

    # 2. เติมข้อมูลให้ไฟล์แต่ละเดือนครบทุกชีต
    # 2.1 ต้นทุนดีไวน์-2569-05.xlsx (2026-05)
    s5, o5 = make_synthetic_month_data("2026-05", master_sku, n_orders=950, seed=505)
    a5 = make_ads_df("2026-05", seed=505)
    write_workbook_clean(ROOT / "ต้นทุนดีไวน์-2569-05.xlsx", master_sku, s5, o5, a5, "OrderSKUList", "ads")
    print("   Filled ต้นทุนดีไวน์-2569-05.xlsx")

    # 2.2 ต้นทุนดีไวน์2569-06.xlsx (2026-06)
    s6, o6 = make_synthetic_month_data("2026-06", master_sku, n_orders=1250, seed=606)
    a6 = make_ads_df("2026-06", seed=606)
    write_workbook_clean(ROOT / "ต้นทุนดีไวน์2569-06.xlsx", master_sku, s6, o6, a6, "Order6", "ads")
    print("   Filled ต้นทุนดีไวน์2569-06.xlsx")

    # 2.3 ต้นทุนดีไวน์2569-07-1.xlsx (2026-07 - มีรายละเอียดคำสั่งซื้อจริง 2,399 แถว)
    w7 = load_workbook(str(ROOT / "ต้นทุนดีไวน์2569-07-1.xlsx"))
    s7 = w7.settlement if not w7.settlement.empty else make_synthetic_month_data("2026-07", master_sku, 1500, 707)[0]
    o7 = build_orders_for_existing_settlement(s7, master_sku, seed=707)
    a7 = make_ads_df("2026-07", seed=707)
    write_workbook_clean(ROOT / "ต้นทุนดีไวน์2569-07-1.xlsx", master_sku, s7, o7, a7, "Order7", "ads")
    print("   Filled ต้นทุนดีไวน์2569-07-1.xlsx")

    # 2.4 ต้นทุนดีไวน์2569-08.xlsx (2026-08)
    s8_div, o8_div = make_synthetic_month_data("2026-08", master_sku, n_orders=1680, seed=808)
    a8_div = make_ads_df("2026-08", seed=808)
    write_workbook_clean(ROOT / "ต้นทุนดีไวน์2569-08.xlsx", master_sku, s8_div, o8_div, a8_div, "Order8", "ads")
    print("   Filled ต้นทุนดีไวน์2569-08.xlsx")

    # 2.5 ต้นทุน2569-08.xlsx (2026-08 ชุดที่ 2)
    s8_main, o8_main = make_synthetic_month_data("2026-08", master_sku, n_orders=2450, seed=818)
    a8_main = make_ads_df("2026-08", seed=818)
    write_workbook_clean(ROOT / "ต้นทุน2569-08.xlsx", master_sku, s8_main, o8_main, a8_main, "Order8", "ads")
    print("   Filled ต้นทุน2569-08.xlsx")

    # 2.6 ต้นทุนดีไวน์2569-09.xlsx (2026-09 - มี Order9 จริง 3,691 แถว)
    w9_div = load_workbook(str(ROOT / "ต้นทุนดีไวน์2569-09.xlsx"))
    o9_div = w9_div.orders
    if "Product Category" not in o9_div.columns:
        cat_map = dict(zip(master_sku["รหัส"], master_sku["หมวดหมู่"]))
        o9_div["Product Category"] = o9_div["Seller SKU"].map(cat_map).fillna("ครีมบำรุงผิวและโลชั่น")
    s9_div = build_settlement_for_existing_orders(o9_div, "2026-09", seed=901)
    a9_div = make_ads_df("2026-09", seed=901)
    write_workbook_clean(ROOT / "ต้นทุนดีไวน์2569-09.xlsx", master_sku, s9_div, o9_div, a9_div, "Order9", "แคมเปญ")
    print("   Filled ต้นทุนดีไวน์2569-09.xlsx")

    # 2.7 ต้นทุน2569-09.xlsx (ไฟล์ใหญ่ 32,779 แถว)
    update_large_2569_09(ROOT / "ต้นทุน2569-09.xlsx", master_sku)
    print("   Filled ต้นทุน2569-09.xlsx")

    # 3. ล้างข้อมูลจำลองในฐานข้อมูลของแอปทั้งหมด (Snapshots, Fixed Costs, SKUs)
    print("3. Clearing pre-populated database & snapshots...")
    snap_dir = APP_DIR / "data" / "snapshots"
    if snap_dir.exists():
        for p in snap_dir.glob("*.parquet"):
            p.unlink(missing_ok=True)
    with db.connect() as c:
        c.execute("DELETE FROM monthly_snapshots")
        c.execute("DELETE FROM fixed_costs")
        c.execute("DELETE FROM sku")
    print("   Cleared monthly_snapshots, fixed_costs, sku, and parquet files!")


if __name__ == "__main__":
    main()
