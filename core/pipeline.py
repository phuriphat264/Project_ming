"""Data Pipeline: คำนวณต้นทุนและกำไรอัตโนมัติตามโครงสร้างไฟล์จริงของ TikTok Shop และบริษัท

แทนที่สูตรในไฟล์ Excel ของฝ่ายบัญชีแบบครบถ้วน:
1. ชีต Order (Order8, Order7, ...):
   - ราคาต่อหน่วย (Col I) = VLOOKUP(Seller SKU, SKU!A:C, 3, FALSE)
   - มูลค่าตามสั่งซื้อ      = ราคาต่อหน่วย * Quantity
   - มูลค่าต้นทุนสุทธิ (Col J) = ราคาต่อหน่วย * (Quantity - Sku Quantity of return) [ยกเว้นออเดอร์ยกเลิก = 0]
2. ชีต รายละเอียดคำสั่งซื้อ:
   - ยอดการชำระเงินทั้งหมด (Col F) = รายได้ทั้งหมด + ค่าธรรมเนียมทั้งหมด + จำนวนการปรับยอด
   - ต้นทุนรวม (Col G)           = SUMIFS(Order!J:J, Order!A:A, รายละเอียดคำสั่งซื้อ!A) [ตัดออเดอร์คืนเงินเต็มจำนวน = 0 อัตโนมัติ]
   - กำไรรายออเดอร์ (Col H)       = ยอดการชำระเงินทั้งหมด (F) - ต้นทุนรวม (G)
   - แยกรายการ 'การชำระเงินด้วย GMV สำหรับโฆษณา TikTok / โปรโมท' ออกจากค่าธรรมเนียมและการปรับยอดทั่วไปอย่างชัดเจน
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

import pandas as pd

from .loader import (
    ORDER_KEY,
    SETTLEMENT_KEY,
    SETTLEMENT_NUMERIC,
    LoadedWorkbook,
)

CANCELLED_STATUSES = {"ยกเลิกแล้ว", "Cancelled", "Canceled"}
ALL_PERIODS_KEY = "📊 สรุปรวมทุกงวดทั้งหมด"
GMV_ADS_TXN_TYPES = {
    "การชำระเงินด้วย GMV สำหรับโฆษณา TikTok",
    "การชำระเงินด้วย GMV สำหรับการโปรโมท",
}

AFFILIATE_TOP_COLS = [
    "ค่าคอมมิชชั่นแอฟฟิลิเอต",
    "ค่าคอมมิชชั่นของพาร์ทเนอร์แอฟฟิลิเอต",
    "ค่าคอมมิชชั่นแอฟฟิลิเอตสำหรับโฆษณาร้านค้า",
    "เงินมัดจำค่าคอมมิชชั่นของแอฟฟิลิเอต",
    "การคืนเงินค่าคอมมิชชั่นแอฟฟิลิเอต",
    "ค่าคอมมิชชั่นโฆษณาร้านค้าพาร์ทเนอร์แอฟฟิลิเอต",
]

CAMPAIGN_SERVICE_COLS = [
    "ค่าธรรมเนียมการบริการ SFP",
    "ค่าธรรมเนียมบริการคืนเงินโบนัส",
    "ค่าบริการของคูปองไลฟ์คุ้ม",
    "ค่าบริการคูปอง Xtra",
    "ค่าบริการโปรแกรม EAMS",
    "ค่าบริการแบรนด์ดัง ลดแรง/แฟลชเซล",
    "ค่าทรัพยากรแคมเปญ",
]

INFRA_OTHER_FEE_COLS = [
    "ค่าธรรมเนียมโปรแกรม TikTok PayLater",
    "ค่าธรรมเนียมโครงสร้างพื้นฐาน",
    "ค่าธรรมเนียมพรีออเดอร์",
    "Guarantee program fee",
]

GMV_MAX_ORDER_COLS = [
    "คูปอง GMV Max",
    "ภาษีการขายสำหรับคูปอง GMV Max",
    "ค่าโฆษณา GMV Max",
]

ORDER_RESULT_COLS = [
    "order_id",
    "txn_type",
    "created_date",
    "date",
    "category",
    "units",
    "gross_sales_before_discount",
    "seller_discount",
    "gross_sales",
    "refunds_before_discount",
    "refund_seller_discount",
    "refunds",
    "net_sales",
    "platform_fees",
    "order_fee",
    "tiktok_commission",
    "commission",
    "credit_card_fee",
    "shipping",
    "affiliate",
    "growth_fee",
    "campaign_service_fee",
    "infra_and_other_fee",
    "gmv_max_order_fee",
    "gmv_ads_deduction",
    "gmv_ads",
    "other_adjustment",
    "adjustment",
    "customer_payment",
    "platform_discount",
    "net_settlement",
    "cogs",
    "profit",
    "cost_missing",
]


@dataclass
class PipelineResult:
    orders: pd.DataFrame          # 1 แถวต่อ 1 รายการในรายละเอียดคำสั่งซื้อ พร้อม ยอดชำระ(F) - ต้นทุน(G) = กำไร(H)
    order_lines: pd.DataFrame     # 1 แถวต่อ SKU ในชีต Order พร้อม ราคาต่อหน่วย(I) และ มูลค่า(J)
    ads: pd.DataFrame             # ชีตโฆษณาภายนอก (ถ้ามี)
    missing_skus: pd.DataFrame    # SKU ที่ยังไม่มีราคาทุน (แทนปัญหา #N/A เดิม)
    source: str                   # "settlement" หรือ "orders_only"
    warnings: list[str] = field(default_factory=list)
    fee_details: dict[str, float] = field(default_factory=dict)  # ยอดรวมทุกคอลัมน์สำหรับสร้างตาราง 'รายงาน' ของ TikTok
    withdrawals: pd.DataFrame = field(default_factory=pd.DataFrame)  # ชีตบันทึกการถอน (ถ้ามี)
    raw_settlement: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_orders: pd.DataFrame = field(default_factory=pd.DataFrame)
    extra_sheets: dict[str, pd.DataFrame] = field(default_factory=dict)
    shop_code: str = ""


def combine(workbooks: list[LoadedWorkbook]) -> LoadedWorkbook:
    """รวมหลายไฟล์ (เช่น ไฟล์ร้านหลัก + ร้านดีไวน์ หรือไฟล์ Order เดือนก่อนหน้า) เป็นชุดเดียว"""
    merged = LoadedWorkbook(name=", ".join(w.name for w in workbooks))
    settle = [w.settlement for w in workbooks if not w.settlement.empty]
    orders = [w.orders for w in workbooks if not w.orders.empty]
    ads = [w.ads for w in workbooks if not w.ads.empty]
    wds = [w.withdrawals for w in workbooks if not w.withdrawals.empty]
    raw_settle = [w.raw_settlement for w in workbooks if not w.raw_settlement.empty]
    raw_ords = [w.raw_orders for w in workbooks if not w.raw_orders.empty]

    if settle:
        merged.settlement = pd.concat(settle, ignore_index=True).drop_duplicates()
    if raw_settle:
        merged.raw_settlement = pd.concat(raw_settle, ignore_index=True)
    if orders:
        tagged = []
        for w_o in orders:
            tmp_o = w_o.copy()
            sku_c = "SKU ID" if "SKU ID" in tmp_o.columns else "Seller SKU"
            tmp_o["_line_seq"] = tmp_o.groupby([ORDER_KEY, sku_c]).cumcount()
            tagged.append(tmp_o)
        o = pd.concat(tagged, ignore_index=True)
        sku_c = "SKU ID" if "SKU ID" in o.columns else "Seller SKU"
        merged.orders = (
            o.drop_duplicates(subset=[ORDER_KEY, sku_c, "_line_seq"], keep="first")
            .drop(columns=["_line_seq"], errors="ignore")
            .reset_index(drop=True)
        )
    if raw_ords:
        merged.raw_orders = pd.concat(raw_ords, ignore_index=True)
    if ads:
        merged.ads = pd.concat(ads, ignore_index=True).drop_duplicates()
    if wds:
        merged.withdrawals = pd.concat(wds, ignore_index=True).drop_duplicates()
    for w in workbooks:
        for k, v in w.extra_sheets.items():
            if k not in merged.extra_sheets:
                merged.extra_sheets[k] = v
        merged.notes.extend(f"[{w.name}] {n}" for n in w.notes)
    return merged


def extract_order_skus(orders: pd.DataFrame) -> pd.DataFrame:
    """ดึงรายการ SKU จากชีต Order พร้อมราคาต่อหน่วย (ถ้ามีใส่ไว้ในชีต Order เช่น Order7/Order8) และราคาตั้งขาย"""
    if orders.empty or "Seller SKU" not in orders.columns:
        return pd.DataFrame(columns=["sku", "name", "category", "unit_cost", "list_price"])
    tmp = orders.copy()
    if "ราคาต่อหน่วย" not in tmp.columns:
        tmp["ราคาต่อหน่วย"] = 0.0
    if "SKU Unit Original Price" not in tmp.columns:
        tmp["SKU Unit Original Price"] = 0.0
    if "Product Category" not in tmp.columns:
        tmp["Product Category"] = ""

    tmp["ราคาต่อหน่วย"] = pd.to_numeric(tmp["ราคาต่อหน่วย"], errors="coerce").fillna(0.0)
    tmp["SKU Unit Original Price"] = pd.to_numeric(tmp["SKU Unit Original Price"], errors="coerce").fillna(0.0)

    # กรอง Seller SKU: ไม่เอาค่าว่าง และไม่เอาตัวเลขล้วน 10 หลักขึ้นไป (ป้องกัน TikTok SKU ID หลุดเข้ามาเป็น SKU)
    tmp["Seller SKU"] = tmp["Seller SKU"].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
    tmp = tmp[(tmp["Seller SKU"] != "") & (~tmp["Seller SKU"].str.fullmatch(r"\d{10,}"))]
    if tmp.empty:
        return pd.DataFrame(columns=["sku", "name", "category", "unit_cost", "list_price"])

    grouped = (
        tmp.groupby("Seller SKU")
        .agg(
            name=("Product Name", "first"),
            category=("Product Category", "first"),
            unit_cost=("ราคาต่อหน่วย", "max"),
            list_price=("SKU Unit Original Price", "max"),
        )
        .reset_index()
        .rename(columns={"Seller SKU": "sku"})
    )
    return grouped


def build_order_lines(orders: pd.DataFrame, sku_master: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ ราคาต่อหน่วย (Col I) และ มูลค่า (Col J) ในชีต Order"""
    if orders.empty:
        return pd.DataFrame()
    lines = orders.copy()

    # ตรวจสอบสูตรมาตรฐานของชีต Order จาก TikTok กรณีบางแถวเป็นค่าว่าง
    for col in (
        "Quantity",
        "Sku Quantity of return",
        "SKU Unit Original Price",
        "SKU Subtotal Before Discount",
        "SKU Platform Discount",
        "SKU Seller Discount",
        "SKU Subtotal After Discount",
        "Original Shipping Fee",
        "Shipping Fee Seller Discount",
        "Shipping Fee Platform Discount",
        "Shipping Fee After Discount",
    ):
        if col not in lines.columns:
            lines[col] = 0.0
        lines[col] = pd.to_numeric(lines[col], errors="coerce").fillna(0.0)

    # SKU Subtotal After Discount = SKU Subtotal Before Discount - SKU Platform Discount - SKU Seller Discount
    calc_sub_after = (
        lines["SKU Subtotal Before Discount"] - lines["SKU Platform Discount"] - lines["SKU Seller Discount"]
    ).clip(lower=0.0)
    lines["SKU Subtotal After Discount"] = lines["SKU Subtotal After Discount"].where(
        lines["SKU Subtotal After Discount"] > 0, calc_sub_after
    )

    status = lines.get("Order Status", pd.Series("", index=lines.index)).astype(str).str.strip()
    lines["is_cancelled"] = status.isin(CANCELLED_STATUSES)

    # เตรียมตาราง SKU Master
    m_cols = ["sku", "name", "category", "unit_cost"]
    master = sku_master.copy() if not sku_master.empty else pd.DataFrame(columns=m_cols)
    for mc in m_cols:
        if mc not in master.columns:
            master[mc] = 0.0 if mc == "unit_cost" else ""
    master = master[m_cols].rename(columns={"sku": "Seller SKU"})

    # ลบคอลัมน์คำนวณเดิมก่อน merge (เผื่อคำนวณซ้ำ)
    for drop_c in ("name", "category", "unit_cost", "cost_missing", "net_qty", "line_cost", "gross_line_cost", "product_name"):
        if drop_c in lines.columns:
            lines = lines.drop(columns=[drop_c])

    # ทำความสะอาด Seller SKU (ไม่นำ SKU ID มาแทนที่ Seller SKU)
    if "Seller SKU" not in lines.columns:
        lines["Seller SKU"] = ""
    else:
        lines["Seller SKU"] = lines["Seller SKU"].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
        # หากมีค่าตัวเลขล้วน 10 หลักขึ้นไปที่อาจเคยหลุดมาจาก SKU ID ให้ล้างออกเป็นค่าว่าง
        lines["Seller SKU"] = lines["Seller SKU"].mask(lines["Seller SKU"].str.fullmatch(r"\d{10,}"), "")

    # หาก Seller SKU ว่างอยู่ ให้ตรวจดูตาราง product_sku_mappings ที่ผู้ใช้เคยจับคู่/กำหนดรหัสไว้
    if "Product Name" in lines.columns:
        try:
            from .db import get_sku_mappings
            p_mappings = get_sku_mappings()
            if p_mappings:
                clean_pn = lines["Product Name"].fillna("").astype(str).str.strip()
                empty_sku_mask = lines["Seller SKU"] == ""
                if empty_sku_mask.any():
                    mapped = clean_pn[empty_sku_mask].map(p_mappings)
                    can_fill_map = mapped.notna() & (mapped != "")
                    if can_fill_map.any():
                        lines.loc[mapped[can_fill_map].index, "Seller SKU"] = mapped[can_fill_map]
        except Exception:
            pass

    lines = lines.merge(master, on="Seller SKU", how="left")
    lines["cost_missing"] = lines["unit_cost"].isna() | (lines["unit_cost"] <= 0)
    lines["unit_cost"] = pd.to_numeric(lines["unit_cost"], errors="coerce").fillna(0.0)

    # Fallback เสริม: ถ้ายังหาราคาทุนไม่เจอ ลองจับคู่ด้วยชื่อสินค้าจาก master
    if lines["cost_missing"].any() and "Product Name" in lines.columns:
        valid_m = master[master["unit_cost"] > 0].dropna(subset=["name"]).copy()
        if not valid_m.empty:
            # 1. ลองจับคู่ชื่อตรงกันทุกตัวอักษร
            name_to_cost = dict(zip(valid_m["name"].str.strip(), valid_m["unit_cost"]))
            name_to_sku = dict(zip(valid_m["name"].str.strip(), valid_m["Seller SKU"]))
            clean_names = lines.loc[lines["cost_missing"], "Product Name"].astype(str).str.strip()
            filled = clean_names.map(name_to_cost)
            can_fill = filled.notna() & (filled > 0)
            if can_fill.any():
                fill_idx = filled[can_fill].index
                lines.loc[fill_idx, "unit_cost"] = filled[can_fill]
                lines.loc[fill_idx, "cost_missing"] = False
                # ถ้าแถวนี้ Seller SKU ว่างอยู่ ให้ดึงรหัส Seller SKU จาก master มาใส่ให้อัตโนมัติ
                empty_sku_mask = lines.loc[fill_idx, "Seller SKU"] == ""
                if empty_sku_mask.any():
                    match_skus = clean_names.loc[fill_idx[empty_sku_mask]].map(name_to_sku)
                    lines.loc[fill_idx[empty_sku_mask], "Seller SKU"] = match_skus.fillna("")

            # 2. จับคู่ชื่อแบบ Normalize (ตัด #รหัส, (GMV), (ชุดที่..), ขนาด.. เพื่อดึง Seller SKU และต้นทุนจริง)
            still_missing = lines["cost_missing"] & (lines["Product Name"].fillna("") != "")
            if still_missing.any():
                def _norm_pname(s: str) -> str:
                    s = str(s).strip()
                    s = re.sub(r'#\d+', '', s)
                    s = re.sub(r'\(GMV\)', '', s, flags=re.I)
                    s = re.sub(r'\(ชุดที่\s*\d+\)', '', s)
                    s = re.sub(r'โปร[^\s]+', '', s)
                    s = re.sub(r'\+?\s*\d+\.\d+', '', s)
                    s = re.sub(r'ลดสุดใจ', '', s)
                    s = re.sub(r'วันเงินออก', '', s)
                    s = re.sub(r'ใหม่ล่าสุด', '', s)
                    s = re.sub(r'ด่วน', '', s)
                    s = re.sub(r'สูตร\s*\d+', '', s)
                    s = re.sub(r'ขนาด\s*\d+(?:\.\d+)?\s*(?:กรัม|ml|มล\.?|g)', '', s, flags=re.I)
                    s = re.sub(r'\s+', ' ', s)
                    return s.strip()

                norm_m_cost = {}
                norm_m_sku = {}
                for _, mr in valid_m.iterrows():
                    nm = _norm_pname(mr["name"])
                    if nm and nm not in norm_m_cost:
                        norm_m_cost[nm] = mr["unit_cost"]
                        norm_m_sku[nm] = mr["Seller SKU"]

                miss_norm = lines.loc[still_missing, "Product Name"].apply(_norm_pname)
                filled_norm = miss_norm.map(norm_m_cost)
                can_fill_norm = filled_norm.notna() & (filled_norm > 0)
                if can_fill_norm.any():
                    fn_idx = filled_norm[can_fill_norm].index
                    lines.loc[fn_idx, "unit_cost"] = filled_norm[can_fill_norm]
                    lines.loc[fn_idx, "cost_missing"] = False
                    empty_sku_mask2 = lines.loc[fn_idx, "Seller SKU"] == ""
                    if empty_sku_mask2.any():
                        match_skus2 = miss_norm.loc[fn_idx[empty_sku_mask2]].map(norm_m_sku)
                        lines.loc[fn_idx[empty_sku_mask2], "Seller SKU"] = match_skus2.fillna("")

    # คำนวณจำนวนขายสุทธิ และคอลัมน์ I (ราคาต่อหน่วย), คอลัมน์ J (มูลค่า)
    returned = lines["Sku Quantity of return"]
    lines["net_qty"] = (lines["Quantity"] - returned).clip(lower=0.0)
    lines.loc[lines["is_cancelled"], "net_qty"] = 0.0

    lines["ราคาต่อหน่วย"] = lines["unit_cost"]
    lines["gross_line_cost"] = lines["unit_cost"] * lines["Quantity"]  # ตรงกับสูตรดิบ =+I*L
    lines["line_cost"] = lines["unit_cost"] * lines["net_qty"]         # มูลค่าสุทธิ (หักยกเลิก/ตีกลับอัตโนมัติ)
    lines["มูลค่า"] = lines["line_cost"]

    # หมวดหมู่: ใช้จาก SKU master ก่อน ถ้าว่างใช้ Product Category จากชีต Order ของ TikTok
    tiktok_cat = lines.get("Product Category", pd.Series("", index=lines.index)).fillna("").astype(str).str.strip()
    lines["category"] = lines["category"].fillna("").astype(str).str.strip()
    lines["category"] = lines["category"].where(lines["category"] != "", tiktok_cat)
    lines["category"] = lines["category"].replace("", "ไม่ระบุหมวดหมู่").fillna("ไม่ระบุหมวดหมู่")

    prod_name = lines.get("Product Name", pd.Series("", index=lines.index)).fillna("")
    lines["product_name"] = lines["name"].where(lines["name"].fillna("") != "", prod_name)
    return lines


def find_missing_skus(lines: pd.DataFrame) -> pd.DataFrame:
    cols = ["sku", "name", "category", "qty", "orders_count"]
    if lines.empty:
        return pd.DataFrame(columns=cols)
    miss = lines[lines["cost_missing"] & ~lines["is_cancelled"] & (lines["net_qty"] > 0)].copy()
    if miss.empty:
        miss = lines[lines["cost_missing"]].copy()
        if miss.empty:
            return pd.DataFrame(columns=cols)
    sku_c = "Seller SKU" if "Seller SKU" in miss.columns else miss.columns[0]
    p_name = "Product Name" if "Product Name" in miss.columns else sku_c
    cat_c = "category" if "category" in miss.columns else sku_c
    q_col = "net_qty" if "net_qty" in miss.columns else ("Quantity" if "Quantity" in miss.columns else sku_c)
    o_col = ORDER_KEY if ORDER_KEY in miss.columns else miss.columns[0]

    # ทำความสะอาด Seller SKU: ถ้าว่าง หรือเป็นเลขล้วน 10 หลักขึ้นไป ให้ระบุเป็น (ไม่ระบุ SKU)
    clean_sku = miss[sku_c].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
    clean_sku = clean_sku.mask(clean_sku.str.fullmatch(r"\d{10,}"), "")
    miss["_display_sku"] = clean_sku.where(clean_sku != "", "(ไม่ระบุ SKU)")

    # จัดกลุ่มโดยใช้ _display_sku ร่วมกับ p_name เพื่อไม่ให้สินค้าที่ไม่มี SKU คนละรายการถูกยุบรวมกัน
    return (
        miss.groupby(["_display_sku", p_name], dropna=False)
        .agg(
            category=(cat_c, "first"),
            qty=(q_col, "sum") if q_col != sku_c else ("count", "sum"),
            orders_count=(o_col, "nunique"),
        )
        .reset_index()
        .rename(columns={"_display_sku": "sku", p_name: "name"})
        .sort_values("qty", ascending=False)
    )[cols]


def _order_level_from_lines(lines: pd.DataFrame) -> pd.DataFrame:
    """สรุปต้นทุนรวมต่อ Order ID (=SUMIFS(Order!J:J, Order!A:A, A)) + หมวดหมู่หลัก"""
    agg = lines.groupby(ORDER_KEY).agg(
        cogs=("line_cost", "sum"),
        units=("net_qty", "sum"),
        cost_missing=("cost_missing", "any"),
        is_cancelled=("is_cancelled", "all"),
    )
    main_cat = (
        lines.sort_values("SKU Subtotal After Discount", ascending=False)
        .groupby(ORDER_KEY)["category"]
        .first()
    )
    agg["category"] = main_cat
    return agg.reset_index()


def _sum_cols(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    present = [c for c in cols if c in df.columns]
    if not present:
        return pd.Series(0.0, index=df.index)
    return df[present].sum(axis=1)


def _extract_fee_details(s: pd.DataFrame) -> dict[str, float]:
    """รวบรวมยอดรวมของทุกคอลัมน์ในชีตรายละเอียดคำสั่งซื้อ เพื่อสร้างตาราง 'รายงาน' ของ TikTok แบบครบทุกบรรทัด"""
    details: dict[str, float] = {}
    for col in SETTLEMENT_NUMERIC:
        if col in s.columns:
            val = float(pd.to_numeric(s[col], errors="coerce").fillna(0.0).sum())
            if abs(val) > 1e-9:
                details[col] = round(val, 2)

    if "ประเภทธุรกรรม" in s.columns and "จำนวนการปรับยอด" in s.columns:
        non_order = s[s["ประเภทธุรกรรม"].astype(str).str.strip() != "คำสั่งซื้อ"]
        if not non_order.empty:
            adj_grp = non_order.groupby("ประเภทธุรกรรม")["จำนวนการปรับยอด"].sum()
            for txn_name, val in adj_grp.items():
                if abs(float(val)) > 1e-9:
                    details[f"adj::{str(txn_name).strip()}"] = round(float(val), 2)
    return details


def ensure_order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """รับประกันว่า DataFrame ของ orders มีคอลัมน์ครบถ้วน (รองรับการเปิด Snapshot เก่าที่บันทึกไว้ก่อนอัปเกรด)"""
    if df.empty:
        return pd.DataFrame(columns=ORDER_RESULT_COLS)
    o = df.copy()
    if "created_date" not in o.columns:
        o["created_date"] = o.get("date")
    if "gross_sales_before_discount" not in o.columns:
        o["gross_sales_before_discount"] = o.get("gross_sales", 0.0)
    if "seller_discount" not in o.columns:
        o["seller_discount"] = 0.0
    if "refunds_before_discount" not in o.columns:
        o["refunds_before_discount"] = o.get("refunds", 0.0)
    if "refund_seller_discount" not in o.columns:
        o["refund_seller_discount"] = 0.0
    if "order_fee" not in o.columns:
        o["order_fee"] = 0.0
    if "tiktok_commission" not in o.columns:
        o["tiktok_commission"] = o.get("commission", 0.0)
    if "credit_card_fee" not in o.columns:
        o["credit_card_fee"] = 0.0
    if "growth_fee" not in o.columns:
        o["growth_fee"] = 0.0
    if "campaign_service_fee" not in o.columns:
        o["campaign_service_fee"] = 0.0
    if "infra_and_other_fee" not in o.columns:
        known = (
            o.get("commission", 0.0)
            + o.get("affiliate", 0.0)
            + o.get("shipping", 0.0)
            + o.get("gmv_ads", 0.0)
        )
        o["infra_and_other_fee"] = (o.get("platform_fees", 0.0) - known).clip(lower=0.0)
    if "gmv_max_order_fee" not in o.columns:
        o["gmv_max_order_fee"] = o.get("gmv_ads", 0.0)
    if "gmv_ads_deduction" not in o.columns:
        is_gmv = o.get("txn_type", pd.Series("", index=o.index)).astype(str).isin(GMV_ADS_TXN_TYPES)
        adj = pd.to_numeric(o.get("adjustment", 0.0), errors="coerce").fillna(0.0)
        o["gmv_ads_deduction"] = (-adj).where(is_gmv, 0.0)
    if "other_adjustment" not in o.columns:
        is_gmv = o.get("txn_type", pd.Series("", index=o.index)).astype(str).isin(GMV_ADS_TXN_TYPES)
        adj = pd.to_numeric(o.get("adjustment", 0.0), errors="coerce").fillna(0.0)
        o["other_adjustment"] = adj.where(~is_gmv, 0.0)
    if "customer_payment" not in o.columns:
        o["customer_payment"] = 0.0
    if "platform_discount" not in o.columns:
        o["platform_discount"] = 0.0
    for c in ORDER_RESULT_COLS:
        if c not in o.columns:
            o[c] = False if c == "cost_missing" else ("" if c in ("order_id", "txn_type", "category") else 0.0)
    return o[ORDER_RESULT_COLS]


def _non_sale_row_mask(df: pd.DataFrame) -> pd.Series:
    """ระบุแถวที่ไม่ใช่การขายสินค้าจริง (เช่น โฆษณา GMV, ปรับยอด, คืนเงินเต็มจำนวน หรือคืนเงินย้อนหลังครบ 100%)"""
    gross_before = pd.to_numeric(df.get("gross_sales_before_discount", 0.0), errors="coerce").fillna(0.0)
    base_mask = (
        (df["txn_type"] != "คำสั่งซื้อ")
        | ((df["net_sales"] <= 0) & (df["refunds"] < 0))
        | ((df["net_sales"] <= 0) & (df["gross_sales"] <= 0) & (gross_before <= 0))
    )
    ord_rows = df["txn_type"] == "คำสั่งซื้อ"
    if ord_rows.any() and df.loc[ord_rows, "order_id"].duplicated().any():
        grp_sales = df.loc[ord_rows].groupby("order_id")["net_sales"].transform("sum")
        grp_ref = df.loc[ord_rows].groupby("order_id")["refunds"].transform("sum")
        full_post_refund = pd.Series(False, index=df.index)
        full_post_refund.loc[ord_rows] = (grp_sales <= 1e-6) & (grp_ref < -1e-6)
        base_mask = base_mask | full_post_refund
    return base_mask


def _deduplicate_order_cogs(df: pd.DataFrame, non_sale_mask: pd.Series) -> pd.DataFrame:
    """ป้องกันการคิดต้นทุน (COGS) และจำนวนชิ้นซ้ำซ้อน กรณี Order ID เดียวกันมีหลายแถวใน Settlement"""
    out = df.copy()
    out.loc[non_sale_mask, ["cogs", "units"]] = 0.0
    out.loc[non_sale_mask, "cost_missing"] = False

    elig_idx = out.index[~non_sale_mask]
    if len(elig_idx) > 1:
        elig = out.loc[elig_idx]
        if elig["order_id"].duplicated().any():
            sort_cols = [c for c in ("gross_sales", "gross_sales_before_discount", "net_settlement") if c in elig.columns]
            ranked = elig.sort_values(sort_cols, ascending=False, kind="mergesort") if sort_cols else elig
            dup_idx = ranked.index[ranked.duplicated(subset=["order_id"], keep="first")]
            if len(dup_idx) > 0:
                out.loc[dup_idx, ["cogs", "units"]] = 0.0
                out.loc[dup_idx, "cost_missing"] = False
    return out


def build_order_row_keys(o: pd.DataFrame) -> list[tuple]:
    """สร้างคีย์จำแนกแถวธุรกรรมเพื่อตัดซ้ำข้าม Snapshot โดยไม่ตัดรายการคืนเงิน/ปรับยอดคนละเดือนทิ้ง"""
    if o.empty:
        return []
    dates = pd.to_datetime(o["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    oids = o["order_id"].astype(str)
    txns = o["txn_type"].astype(str)
    f_vals = pd.to_numeric(o["net_settlement"], errors="coerce").fillna(0.0).round(2)
    s_vals = pd.to_numeric(o["net_sales"], errors="coerce").fillna(0.0).round(2)
    counts: dict[tuple, int] = {}
    keys: list[tuple] = []
    for oid, txn, dt_s, fv, sv in zip(oids, txns, dates, f_vals, s_vals):
        base_k = (oid, txn, dt_s, float(fv), float(sv))
        occ = counts.get(base_k, 0)
        counts[base_k] = occ + 1
        keys.append((*base_k, occ))
    return keys


def run_pipeline(data: LoadedWorkbook, sku_master: pd.DataFrame, shop_code: str = "") -> PipelineResult:
    warnings: list[str] = []
    eff_master = sku_master if (sku_master is not None and not sku_master.empty) else extract_order_skus(data.orders)
    lines = build_order_lines(data.orders, eff_master)
    missing = find_missing_skus(lines)
    if not missing.empty:
        warnings.append(f"พบ {len(missing)} SKU ที่ยังไม่มีราคาทุน — ต้นทุนของรายการเหล่านี้จะถูกนับเป็น 0")

    fee_details: dict[str, float] = {}

    if not data.settlement.empty:
        s = data.settlement.copy()
        fee_details = _extract_fee_details(s)

        s["order_id"] = s[SETTLEMENT_KEY].astype(str).str.strip()
        s["txn_type"] = s.get("ประเภทธุรกรรม", pd.Series("คำสั่งซื้อ", index=s.index)).fillna("คำสั่งซื้อ").astype(str).str.strip()
        s["created_date"] = s.get("เวลาที่สร้างคำสั่งซื้อ")
        s["date"] = s.get("เวลาที่ชำระคำสั่งซื้อ", s.get("เวลาที่สร้างคำสั่งซื้อ"))

        # 1. รายได้ทั้งหมด และส่วนประกอบตามรายงาน TikTok
        s["gross_sales_before_discount"] = s["ยอดรวมค่าสินค้าก่อนหักส่วนลด"]
        s["seller_discount"] = s["ส่วนลดจากร้านค้า"]
        s["gross_sales"] = s["ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย"]
        s["refunds_before_discount"] = s["ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า"]
        s["refund_seller_discount"] = s["เงินคืนจากส่วนลดร้านค้า"]
        s["refunds"] = s["ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย"]
        s["net_sales"] = s["รายได้ทั้งหมด"]

        # 2. ค่าธรรมเนียมทั้งหมด (เก็บเป็นค่าบวกเพื่อให้แสดงค่าใช้จ่ายเข้าใจง่าย)
        s["platform_fees"] = -s["ค่าธรรมเนียมทั้งหมด"]
        s["order_fee"] = -s["ค่าธรรมเนียมคำสั่งซื้อ"]
        s["tiktok_commission"] = -s["ค่าคอมมิชชั่น TikTok Shop"]
        s["commission"] = s["order_fee"] + s["tiktok_commission"]
        s["credit_card_fee"] = -s["การผ่อนชำระด้วยบัตรเครดิต - มีอัตราดอกเบี้ย"]
        s["shipping"] = -s["ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง"]
        s["affiliate"] = -_sum_cols(s, AFFILIATE_TOP_COLS)
        s["growth_fee"] = -s["ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า"]
        s["campaign_service_fee"] = -_sum_cols(s, CAMPAIGN_SERVICE_COLS)
        s["infra_and_other_fee"] = -_sum_cols(s, INFRA_OTHER_FEE_COLS)
        s["gmv_max_order_fee"] = -_sum_cols(s, GMV_MAX_ORDER_COLS)

        # 3. การปรับยอด — แยก 'การชำระเงินด้วย GMV สำหรับโฆษณา TikTok / โปรโมท' ออกมาอย่างชัดเจน
        raw_col_f = s.get("ยอดการชำระเงินทั้งหมด", pd.Series(0.0, index=s.index))
        s["adjustment"] = s["จำนวนการปรับยอด"]
        # รองรับชีต Settlement แบบย่อที่เหลือเฉพาะคอลัมน์ ยอดการชำระเงินทั้งหมด (เช่น ขายเดือน2บังตี๋)
        non_order_mask = s["txn_type"] != "คำสั่งซื้อ"
        missing_adj = non_order_mask & (s["adjustment"].abs() < 1e-9) & (raw_col_f.abs() > 1e-9)
        s.loc[missing_adj, "adjustment"] = raw_col_f.loc[missing_adj]

        is_gmv_ads = s["txn_type"].isin(GMV_ADS_TXN_TYPES)
        s["gmv_ads_deduction"] = (-s["adjustment"]).where(is_gmv_ads, 0.0)
        s["gmv_ads"] = s["gmv_max_order_fee"] + s["gmv_ads_deduction"]
        s["other_adjustment"] = s["adjustment"].where(~is_gmv_ads, 0.0)

        # กรณีชีต Settlement แบบย่อไม่มีคอลัมน์รายได้และค่าธรรมเนียมเลย ให้ใช้ยอดโอนสุทธิของแถวคำสั่งซื้อเป็นฐานรายได้
        order_mask = s["txn_type"] == "คำสั่งซื้อ"
        if (
            order_mask.any()
            and float(s.loc[order_mask, "net_sales"].abs().sum()) < 1e-9
            and float(s.loc[order_mask, "platform_fees"].abs().sum()) < 1e-9
            and float(raw_col_f.loc[order_mask].abs().sum()) > 1e-9
        ):
            s.loc[order_mask, "net_sales"] = raw_col_f.loc[order_mask]
            s.loc[order_mask, "gross_sales"] = raw_col_f.loc[order_mask].clip(lower=0.0)
            s.loc[order_mask, "refunds"] = raw_col_f.loc[order_mask].clip(upper=0.0)
            warnings.append("ชีตรายละเอียดคำสั่งซื้อเป็นแบบย่อ (มีเฉพาะยอดการชำระเงินทั้งหมด F ไม่มีรายละเอียดค่าธรรมเนียมย่อย)")

        # 4. ข้อมูลสนับสนุนเพิ่มเติม
        s["customer_payment"] = s["การชำระเงินของลูกค้า"] + s["การคืนเงินจากลูกค้า"]
        s["platform_discount"] = s["ส่วนลดจากแพลตฟอร์ม"] + s["การคืนเงินส่วนลดจากแพลตฟอร์ม"]

        # 5. ยอดการชำระเงินทั้งหมด (คอลัมน์ F) = รายได้ทั้งหมด + ค่าธรรมเนียมทั้งหมด + จำนวนการปรับยอด
        calc_settlement = s["net_sales"] - s["platform_fees"] + s["adjustment"]
        use_raw_f = (calc_settlement.abs() < 1e-9) & (raw_col_f.abs() > 1e-9)
        s["net_settlement"] = calc_settlement.where(~use_raw_f, raw_col_f)
        fee_details["ยอดการชำระเงินทั้งหมด"] = round(float(s["net_settlement"].sum()), 2)
        fee_details["รายได้ทั้งหมด"] = round(float(s["net_sales"].sum()), 2)

        # 6. จับคู่ต้นทุนรวมต่อออเดอร์ (คอลัมน์ G = SUMIFS(Order!J:J, Order!A:A, A))
        if not lines.empty:
            cost = _order_level_from_lines(lines)
            s = s.merge(cost, left_on="order_id", right_on=ORDER_KEY, how="left")
            non_sale_row = _non_sale_row_mask(s)
            no_cost = s["cogs"].isna() & (s["txn_type"] == "คำสั่งซื้อ") & ~non_sale_row
            if no_cost.any():
                warnings.append(
                    f"มี {int(no_cost.sum()):,} ออเดอร์ในรายละเอียดคำสั่งซื้อที่ไม่พบในชีต Order "
                    "— ต้นทุนของออเดอร์เหล่านี้จะเป็น 0 (สามารถอัปโหลดชีต Order ของเดือนก่อนหน้าเพิ่มได้)"
                )
            s = _deduplicate_order_cogs(s, non_sale_row)
        else:
            warnings.append("ไม่พบชีต Order — คำนวณต้นทุนสินค้า (COGS) ไม่ได้ จะแสดงเฉพาะรายได้และค่าธรรมเนียม")
            s["cogs"], s["units"], s["cost_missing"], s["category"] = 0.0, 0.0, True, None

        s["cogs"] = s["cogs"].fillna(0.0)
        s["units"] = s["units"].fillna(0.0)
        s["cost_missing"] = s["cost_missing"].fillna(True).astype(bool)
        s["category"] = s["category"].fillna("ไม่ระบุหมวดหมู่")
        s.loc[s["txn_type"] != "คำสั่งซื้อ", "category"] = "รายการปรับยอด / โฆษณา GMV"
        source = "settlement"

    elif not lines.empty:
        warnings.append(
            "ไม่พบชีตรายละเอียดคำสั่งซื้อ (Settlement) — ใช้ยอดขายจากชีต Order (SKU Subtotal After Discount) เป็นค่าประมาณ "
            "และยังไม่รวมค่าธรรมเนียมแพลตฟอร์ม"
        )
        cost = _order_level_from_lines(lines)
        first = (
            lines.groupby(ORDER_KEY)
            .agg(
                created_date=("Created Time", "first"),
                date=("Paid Time", "first"),
                gross_sales_before_discount=("SKU Subtotal Before Discount", "sum"),
                seller_discount=("SKU Seller Discount", lambda x: -x.sum()),
                gross_sales=("SKU Subtotal After Discount", "sum"),
                platform_discount=("SKU Platform Discount", "sum"),
                customer_payment=("Order Amount", "first"),
                refunds=("Order Refund Amount", "first"),
            )
            .reset_index()
        )
        first["date"] = first["date"].where(first["date"].notna(), first["created_date"])
        s = first.merge(cost, on=ORDER_KEY)
        s = s[~s["is_cancelled"]].copy()
        s["order_id"] = s[ORDER_KEY]
        s["txn_type"] = "คำสั่งซื้อ"
        s["refunds"] = -s["refunds"]
        s["refunds_before_discount"] = s["refunds"]
        s["refund_seller_discount"] = 0.0
        s["net_sales"] = s["gross_sales"] + s["refunds"]
        for col in (
            "platform_fees",
            "order_fee",
            "tiktok_commission",
            "commission",
            "credit_card_fee",
            "shipping",
            "affiliate",
            "growth_fee",
            "campaign_service_fee",
            "infra_and_other_fee",
            "gmv_max_order_fee",
            "gmv_ads_deduction",
            "gmv_ads",
            "other_adjustment",
            "adjustment",
        ):
            s[col] = 0.0
        s["net_settlement"] = s["net_sales"]
        source = "orders_only"
    else:
        raise ValueError("ไม่พบข้อมูลที่ใช้ได้ในไฟล์ (ต้องมีชีตรายละเอียดคำสั่งซื้อ หรือชีต Order อย่างน้อย 1 อย่าง)")

    # คอลัมน์ H: กำไรรายออเดอร์ = ยอดการชำระเงินทั้งหมด (F) - ต้นทุนรวม (G)
    s["profit"] = s["net_settlement"] - s["cogs"]
    orders = ensure_order_columns(s).reset_index(drop=True)
    return PipelineResult(
        orders=orders,
        order_lines=lines,
        ads=data.ads,
        missing_skus=missing,
        source=source,
        warnings=warnings,
        fee_details=fee_details,
        withdrawals=data.withdrawals,
        raw_settlement=data.raw_settlement,
        raw_orders=data.raw_orders,
        extra_sheets=data.extra_sheets,
        shop_code=shop_code,
    )


def recalculate_with_skus(res: PipelineResult, sku_master: pd.DataFrame) -> PipelineResult:
    """คำนวณ ราคาต่อหน่วย(I), มูลค่า(J), ต้นทุนรวม(G) และกำไร(H) ใหม่ทันทีเมื่อแก้ไขตาราง SKU"""
    o_base = ensure_order_columns(res.orders)
    if res.order_lines.empty:
        return PipelineResult(
            orders=o_base,
            order_lines=res.order_lines,
            ads=res.ads,
            missing_skus=res.missing_skus,
            source=res.source,
            warnings=res.warnings,
            fee_details=res.fee_details,
            withdrawals=res.withdrawals,
            raw_settlement=res.raw_settlement,
            raw_orders=res.raw_orders,
            extra_sheets=res.extra_sheets,
            shop_code=res.shop_code,
        )

    derived_cols = [
        "is_cancelled",
        "name",
        "category",
        "unit_cost",
        "cost_missing",
        "net_qty",
        "line_cost",
        "gross_line_cost",
        "product_name",
    ]
    raw_orders = res.order_lines.drop(columns=[c for c in derived_cols if c in res.order_lines.columns])
    new_lines = build_order_lines(raw_orders, sku_master)
    new_missing = find_missing_skus(new_lines)
    cost = _order_level_from_lines(new_lines).rename(columns={ORDER_KEY: "order_id"})

    o = o_base.drop(columns=[c for c in ("cogs", "units", "cost_missing", "category") if c in o_base.columns])
    o = o.merge(cost[["order_id", "cogs", "units", "cost_missing", "category"]], on="order_id", how="left")

    non_sale_row = _non_sale_row_mask(o)
    o = _deduplicate_order_cogs(o, non_sale_row)

    o["cogs"] = o["cogs"].fillna(0.0)
    o["units"] = o["units"].fillna(0.0)
    o["cost_missing"] = o["cost_missing"].fillna(True).astype(bool)
    o["category"] = o["category"].fillna("ไม่ระบุหมวดหมู่")
    o.loc[o["txn_type"] != "คำสั่งซื้อ", "category"] = "รายการปรับยอด / โฆษณา GMV"
    o["profit"] = o["net_settlement"] - o["cogs"]

    return PipelineResult(
        orders=ensure_order_columns(o).reset_index(drop=True),
        order_lines=new_lines,
        ads=res.ads,
        missing_skus=new_missing,
        source=res.source,
        warnings=res.warnings,
        fee_details=res.fee_details,
        withdrawals=res.withdrawals,
        raw_settlement=res.raw_settlement,
        raw_orders=res.raw_orders,
        extra_sheets=res.extra_sheets,
        shop_code=res.shop_code,
    )


def _format_shop_period(base_period: str, s_code: str, s_name: str) -> str:
    """สร้างชื่องวดประจำช่องทางโดยไม่ชนกับร้านหลักหรือช่องย่อยอื่น และรักษาความเข้ากันได้กับงวดเดิมในฐานข้อมูล"""
    sc = str(s_code or "").strip().lower()
    if sc == "matang":
        return base_period

    if base_period and sc:
        try:
            from core import db
            snaps = db.list_snapshots(shop_code=sc)
            if not snaps.empty:
                existing = [
                    str(m)
                    for m in snaps["month"].tolist()
                    if str(m).startswith(base_period) and "(รวม)" not in str(m)
                ]
                if len(existing) == 1:
                    return existing[0]
        except Exception:
            pass

    no_paren = re.sub(r"\([^)]*\)", "", str(s_name or "")).strip(" ()[]")
    clean_tag = no_paren if no_paren else sc
    if not clean_tag or clean_tag.lower() == "matang":
        clean_tag = sc or "subshop"
    return f"{base_period} ({clean_tag})"


def detect_period_label(
    result: PipelineResult,
    filenames: list[str] | str = "",
    shop: dict | str | None = None,
) -> str:
    """ตรวจจับงวดเดือน YYYY-MM อัตโนมัติจากวันที่ชำระ/สร้างคำสั่งซื้อ พร้อมแยกป้ายชื่อร้าน (เช่น ดีไวน์)"""
    dates = pd.to_datetime(result.orders["date"], errors="coerce").dropna()
    if dates.empty and "created_date" in result.orders.columns:
        dates = pd.to_datetime(result.orders["created_date"], errors="coerce").dropna()
    if dates.empty and not result.order_lines.empty and "Created Time" in result.order_lines.columns:
        dates = pd.to_datetime(result.order_lines["Created Time"], errors="coerce").dropna()
    base_period = dates.dt.to_period("M").mode()[0].strftime("%Y-%m") if not dates.empty else "ไม่ทราบงวด"

    # 1. หากผู้ใช้เลือก Shop หรือส่ง Shop เข้ามาโดยตรง
    if shop:
        s_code = shop.get("code") if isinstance(shop, dict) else str(shop).lower()
        s_name = shop.get("name") if isinstance(shop, dict) else str(shop)
        return _format_shop_period(base_period, str(s_code or ""), str(s_name or ""))

    # 2. ตรวจจับจากรายชื่อไฟล์
    names_list = [filenames] if isinstance(filenames, str) else list(filenames)
    fnames_joined = " ".join(names_list)

    try:
        from core import db
        detected = db.detect_shop_from_text(fnames_joined)
        if detected:
            return _format_shop_period(base_period, detected["code"], detected["name"])
    except Exception:
        pass

    if len(names_list) > 1 and "ดีไวน์" in fnames_joined:
        has_non_divine = any("ดีไวน์" not in fn for fn in names_list)
        return f"{base_period} (รวม)" if has_non_divine else f"{base_period} (ดีไวน์)"
    if "ดีไวน์" in fnames_joined:
        return f"{base_period} (ดีไวน์)"
    return base_period


def _sync_top_fee_details(fee_details: dict[str, float], o: pd.DataFrame) -> dict[str, float]:
    """อัปเดตยอดรวมหมวดหลักใน fee_details ให้ตรงกับตาราง orders ที่ผ่านการตัดซ้ำ/กรองเดือนแล้ว 100%"""
    fd = dict(fee_details)
    if o.empty:
        return {k: 0.0 for k in fd}
    fd["ยอดการชำระเงินทั้งหมด"] = round(float(o["net_settlement"].sum()), 2)
    fd["รายได้ทั้งหมด"] = round(float(o["net_sales"].sum()), 2)
    fd["ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย"] = round(float(o["gross_sales"].sum()), 2)
    fd["ยอดรวมค่าสินค้าก่อนหักส่วนลด"] = round(float(o["gross_sales_before_discount"].sum()), 2)
    fd["ส่วนลดจากร้านค้า"] = round(float(o["seller_discount"].sum()), 2)
    fd["ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย"] = round(float(o["refunds"].sum()), 2)
    fd["ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า"] = round(float(o["refunds_before_discount"].sum()), 2)
    fd["เงินคืนจากส่วนลดร้านค้า"] = round(float(o["refund_seller_discount"].sum()), 2)
    fd["ค่าธรรมเนียมทั้งหมด"] = round(-float(o["platform_fees"].sum()), 2)
    fd["จำนวนการปรับยอด"] = round(float(o["adjustment"].sum()), 2)
    fd["ค่าธรรมเนียมคำสั่งซื้อ"] = round(-float(o["order_fee"].sum()), 2)
    fd["ค่าคอมมิชชั่น TikTok Shop"] = round(-float(o["tiktok_commission"].sum()), 2)
    fd["การผ่อนชำระด้วยบัตรเครดิต - มีอัตราดอกเบี้ย"] = round(-float(o["credit_card_fee"].sum()), 2)
    fd["ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง"] = round(-float(o["shipping"].sum()), 2)
    fd["ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า"] = round(-float(o["growth_fee"].sum()), 2)

    # คำนวณ adj:: ใหม่จากแถวจริงเพื่อไม่ให้ยอดซ้ำซ้อน
    fd = {k: v for k, v in fd.items() if not k.startswith("adj::")}
    non_order = o[o["adjustment"].abs() > 1e-9]
    if not non_order.empty:
        for txn_t, grp in non_order.groupby("txn_type"):
            val = round(float(grp["adjustment"].sum()), 2)
            if abs(val) > 1e-9:
                fd[f"adj::{txn_t}"] = val
    return fd


def combine_pipeline_results(results: list[PipelineResult], sku_master: pd.DataFrame) -> PipelineResult:
    """รวมข้อมูลงวดที่บันทึกไว้หลายเดือน/หลายร้านเป็นภาพรวมทั้งหมด พร้อมตัดรายการซ้ำซ้อนอัตโนมัติ"""
    if not results:
        empty_o = ensure_order_columns(pd.DataFrame(columns=ORDER_RESULT_COLS))
        return PipelineResult(
            orders=empty_o,
            order_lines=pd.DataFrame(),
            ads=pd.DataFrame(),
            missing_skus=pd.DataFrame(),
            source="settlement",
        )

    seen_keys: set[tuple] = set()
    kept_orders: list[pd.DataFrame] = []
    merged_fd: dict[str, float] = {}

    for r in results:
        o = ensure_order_columns(r.orders)
        if o.empty:
            continue
        keys = build_order_row_keys(o)
        new_mask = pd.Series([k not in seen_keys for k in keys], index=o.index)
        for k in keys:
            seen_keys.add(k)

        new_rows = o[new_mask]
        if new_rows.empty:
            continue
        kept_orders.append(new_rows)

        # ถ้างวดนี้ไม่มีออเดอร์ซ้ำกับงวดก่อนหน้าเลย บวก fee_details ย่อยทุกตัวเข้าด้วยกันได้ตรงๆ
        # ถ้าซ้ำบางส่วน ให้ถ่วงน้ำหนักเฉพาะหมวดย่อยตามสัดส่วนค่าธรรมเนียมของแถวใหม่
        if new_mask.all():
            weight = 1.0
        else:
            tot_fee = float(o["platform_fees"].sum())
            new_fee = float(new_rows["platform_fees"].sum())
            weight = (new_fee / tot_fee) if tot_fee > 0 else (len(new_rows) / len(o))

        for fk, fv in (r.fee_details or {}).items():
            if not fk.startswith("adj::"):
                merged_fd[fk] = round(merged_fd.get(fk, 0.0) + float(fv) * weight, 2)

    all_orders = (
        pd.concat(kept_orders, ignore_index=True)
        if kept_orders
        else ensure_order_columns(pd.DataFrame(columns=ORDER_RESULT_COLS))
    )
    merged_fd = _sync_top_fee_details(merged_fd, all_orders)

    lines_list = [r.order_lines for r in results if r.order_lines is not None and not r.order_lines.empty]
    if lines_list:
        seq_frames = []
        for lf in lines_list:
            lf_c = lf.copy()
            sku_c = "SKU ID" if "SKU ID" in lf_c.columns else "Seller SKU"
            lf_c["_line_seq"] = lf_c.groupby([ORDER_KEY, sku_c], dropna=False).cumcount()
            seq_frames.append(lf_c)
        cat_lines = pd.concat(seq_frames, ignore_index=True)
        sku_c = "SKU ID" if "SKU ID" in cat_lines.columns else "Seller SKU"
        all_lines = (
            cat_lines.drop_duplicates(subset=[ORDER_KEY, sku_c, "_line_seq"], keep="first")
            .drop(columns=["_line_seq"])
            .reset_index(drop=True)
        )
    else:
        all_lines = pd.DataFrame()

    ads_list = [r.ads for r in results if r.ads is not None and not r.ads.empty]
    all_ads = pd.concat(ads_list, ignore_index=True).drop_duplicates().reset_index(drop=True) if ads_list else pd.DataFrame()

    wd_list = [r.withdrawals for r in results if r.withdrawals is not None and not r.withdrawals.empty]
    all_wds = pd.concat(wd_list, ignore_index=True).drop_duplicates().reset_index(drop=True) if wd_list else pd.DataFrame()

    src = "settlement" if any(r.source == "settlement" for r in results) else "orders_only"
    shop_codes = {r.shop_code for r in results if getattr(r, "shop_code", "")}
    common_shop = next(iter(shop_codes)) if len(shop_codes) == 1 else ""
    combined = PipelineResult(
        orders=all_orders,
        order_lines=all_lines,
        ads=all_ads,
        missing_skus=pd.DataFrame(),
        source=src,
        warnings=[],
        fee_details=merged_fd,
        withdrawals=all_wds,
        shop_code=common_shop,
    )
    return recalculate_with_skus(combined, sku_master)


def list_calendar_months(res: PipelineResult) -> list[str]:
    """คืนรายการเดือนปฏิทิน YYYY-MM ทั้งหมดที่ปรากฏในข้อมูลคำสั่งซื้อ (เรียงจากเก่าไปใหม่)"""
    o = ensure_order_columns(res.orders)
    if o.empty:
        return []
    dt = pd.to_datetime(o["date"], errors="coerce")
    if "created_date" in o.columns:
        dt = dt.fillna(pd.to_datetime(o["created_date"], errors="coerce"))
    dt = dt.dropna()
    if dt.empty:
        return []
    return sorted(dt.dt.to_period("M").astype(str).unique().tolist())


def filter_result_by_month(res: PipelineResult, ym: str) -> PipelineResult:
    """กรองข้อมูล PipelineResult เฉพาะเดือนปฏิทิน YYYY-MM ที่เลือก"""
    o = ensure_order_columns(res.orders)
    if o.empty:
        return res
    dt = pd.to_datetime(o["date"], errors="coerce")
    if "created_date" in o.columns:
        dt = dt.fillna(pd.to_datetime(o["created_date"], errors="coerce"))
    ym_series = dt.dt.to_period("M").astype(str)
    sub_o = o[ym_series == ym].reset_index(drop=True)

    tot_fee = float(o["platform_fees"].sum())
    sub_fee = float(sub_o["platform_fees"].sum())
    weight = (sub_fee / tot_fee) if tot_fee > 0 else (len(sub_o) / len(o) if len(o) else 0.0)
    scaled_fd = {
        k: round(float(v) * weight, 2)
        for k, v in (res.fee_details or {}).items()
        if not k.startswith("adj::")
    }
    sub_fd = _sync_top_fee_details(scaled_fd, sub_o)

    if not res.order_lines.empty and ORDER_KEY in res.order_lines.columns:
        valid_ids = set(sub_o["order_id"].astype(str))
        sub_lines = res.order_lines[res.order_lines[ORDER_KEY].astype(str).isin(valid_ids)].reset_index(drop=True)
    else:
        sub_lines = res.order_lines

    sub_ads = res.ads
    if not sub_ads.empty and "วันที่" in sub_ads.columns:
        ad_ym = pd.to_datetime(sub_ads["วันที่"], errors="coerce").dt.to_period("M").astype(str)
        sub_ads = sub_ads[ad_ym == ym].reset_index(drop=True)

    sub_wd = res.withdrawals
    if not sub_wd.empty:
        wd_date_col = next((c for c in ("เวลาส่งคำขอ", "เวลาที่สำเร็จ", "เวลาที่ขอ") if c in sub_wd.columns), None)
        if wd_date_col:
            wd_ym = pd.to_datetime(sub_wd[wd_date_col], errors="coerce").dt.to_period("M").astype(str)
            sub_wd = sub_wd[wd_ym == ym].reset_index(drop=True)

    sub_missing = find_missing_skus(sub_lines) if not sub_lines.empty else pd.DataFrame(columns=["sku", "name", "category", "qty", "orders_count"])
    return PipelineResult(
        orders=sub_o,
        order_lines=sub_lines,
        ads=sub_ads,
        missing_skus=sub_missing,
        source=res.source,
        warnings=res.warnings,
        fee_details=sub_fd,
        withdrawals=sub_wd,
        shop_code=res.shop_code,
    )
