"""สูตรการเงินและการสรุปรายงานตามโครงสร้างจริงของ TikTok Shop และบริษัท มาตัง คอสเมติก จำกัด"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .loader import (
    FEE_DESCRIPTIONS,
    SETTLEMENT_AFFILIATE_SUB_COLS,
    SETTLEMENT_FEE_TOP_COLS,
    SETTLEMENT_SHIPPING_SUB_COLS,
)
from .pipeline import PipelineResult, ensure_order_columns


@dataclass
class Summary:
    gross_sales_before_discount: float  # ยอดรวมค่าสินค้าก่อนหักส่วนลด
    seller_discount: float              # ส่วนลดจากร้านค้า (ค่าติดลบ)
    gross_sales: float                  # ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย
    refunds: float                      # ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย (ค่าติดลบ)
    net_sales: float                    # รายได้ทั้งหมด = gross_sales + refunds
    platform_fees: float                # ค่าธรรมเนียมทั้งหมด (แสดงเป็นค่าบวก)
    gmv_ads_settlement: float           # การชำระเงินด้วย GMV สำหรับโฆษณา TikTok / โปรโมท (หักใน Settlement)
    other_adjustment: float             # การปรับยอดอื่นๆ / เงินชดเชย (บวก = ได้รับเงินเพิ่ม, ลบ = ถูกหัก)
    net_settlement: float               # ยอดการชำระเงินทั้งหมด (คอลัมน์ F) = รายได้ทั้งหมด - ค่าธรรมเนียมทั้งหมด - โฆษณา GMV + ปรับยอดอื่น
    cogs: float                         # มูลค่าต้นทุนสินค้ารวม (คอลัมน์ G = SUMIFS จากชีต Order)
    settlement_profit: float            # กำไรตามชีตรายละเอียดคำสั่งซื้อ (คอลัมน์ H = F - G)
    ads: float                          # ค่าโฆษณาจากชีต Ads ภายนอก (ถ้ามีอัปโหลดแยก)
    total_ads: float                    # รวมค่าโฆษณาทั้งหมด (หักจาก GMV + GMV Max ในออเดอร์ + ชีต Ads)
    rough_profit: float                 # กำไรจากการขาย (ก่อนหักค่าคอมคนขายและค่าใช้จ่ายรายเดือน)
    comm_pct: float                     # % ค่าคอมคนขาย
    sales_commission: float             # ค่าคอมคนขาย (บาท)
    fixed_costs: float                  # ค่าใช้จ่ายโรงงานรายเดือนรวม (ค่าแรง + ค่าน้ำ + ค่าไฟ + อื่นๆ)
    overhead_per_unit: float            # ต้นทุนโรงงานเฉลี่ยต่อชิ้น (แสดงเป็นข้อมูลอ้างอิง)
    gross_profit: float                 # กำไรขั้นต้นก่อนหักค่าธรรมเนียม (รายได้ทั้งหมด - ต้นทุนสินค้า)
    variable_costs: float               # ต้นทุนผันแปรรวม
    contribution_margin: float          # กำไรส่วนเกิน (Contribution Margin)
    net_profit: float                   # กำไรสุทธิสุดท้ายประจำเดือน
    gross_margin_pct: float
    net_margin_pct: float
    cm_ratio: float
    break_even_sales: float | None
    orders: int
    units: float
    losing_orders_count: int
    losing_orders_loss: float
    customer_payment: float             # การชำระเงินของลูกค้าสุทธิ
    platform_discount: float            # ส่วนลดจากแพลตฟอร์มสุทธิ
    order_only_profit: float = 0.0      # กำไรเฉพาะแถว 'คำสั่งซื้อ' ก่อนหักโฆษณา GMV / ปรับยอด (ตรงกับ SUM(H) ใน Excel ที่เว้นแถวปรับยอด)

    def as_dict(self) -> dict:
        return asdict(self)


def _pct(a: float, b: float) -> float:
    return (a / b * 100) if b else 0.0


def _pct_col(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a / b.where(b != 0) * 100).fillna(0.0)


def summarize(
    result: PipelineResult,
    fixed_costs: float = 0.0,
    extra_ads: float | None = None,
    comm_pct: float = 0.0,
    override_sales_commission: float | None = None,
) -> Summary:
    o = ensure_order_columns(result.orders)
    external_ads = (
        float(result.ads["จำนวนรวม"].sum())
        if extra_ads is None and not result.ads.empty and "จำนวนรวม" in result.ads.columns
        else float(extra_ads or 0.0)
    )

    gross_before = float(o["gross_sales_before_discount"].sum())
    seller_disc = float(o["seller_discount"].sum())
    gross_sales = float(o["gross_sales"].sum())
    refunds = float(o["refunds"].sum())
    net_sales = float(o["net_sales"].sum())

    platform_fees = float(o["platform_fees"].sum())
    gmv_ads_settlement = float(o["gmv_ads_deduction"].sum())
    gmv_max_in_fees = float(o["gmv_max_order_fee"].sum())
    other_adjustment = float(o["other_adjustment"].sum())

    # ยอดการชำระเงินทั้งหมด (คอลัมน์ F) = รายได้ทั้งหมด - ค่าธรรมเนียมทั้งหมด - โฆษณา GMV + การปรับยอดอื่น
    net_settlement = float(o["net_settlement"].sum())
    cogs = float(o["cogs"].sum())

    # คอลัมน์ H ในชีตรายละเอียดคำสั่งซื้อ = F - G
    settlement_profit = net_settlement - cogs
    total_ads = gmv_ads_settlement + gmv_max_in_fees + external_ads

    # กำไรจากการขาย (ก่อนหักค่าคอมคนขายและค่าใช้จ่ายรายเดือนตอนท้าย)
    rough_profit = settlement_profit - external_ads
    if override_sales_commission is not None:
        sales_commission = max(0.0, float(override_sales_commission))
    else:
        sales_commission = max(0.0, rough_profit * (comm_pct / 100.0)) if comm_pct > 0 else 0.0

    units = float(o["units"].sum())
    overhead_per_unit = (fixed_costs / units) if units > 0 else 0.0

    gross_profit = net_sales - cogs
    net_deductions_from_sales = net_sales - net_settlement  # ค่าธรรมเนียมทั้งหมด + โฆษณา GMV - ปรับยอดอื่น
    variable = cogs + net_deductions_from_sales + external_ads + sales_commission
    contribution = net_sales - variable
    net_profit = rough_profit - sales_commission - fixed_costs

    cm_ratio = contribution / net_sales if net_sales else 0.0
    bep = (
        fixed_costs / cm_ratio
        if (cm_ratio > 0 and fixed_costs > 0)
        else (0.0 if fixed_costs == 0 and cm_ratio > 0 else None)
    )

    sold = o[o["txn_type"] == "คำสั่งซื้อ"]
    order_only_profit = float(sold["profit"].sum()) if not sold.empty else settlement_profit
    known_sold = sold[~sold["cost_missing"]]
    neg_orders = known_sold[(known_sold["profit"] < 0) & (known_sold["net_sales"] > 0)]

    return Summary(
        gross_sales_before_discount=gross_before,
        seller_discount=seller_disc,
        gross_sales=gross_sales,
        refunds=refunds,
        net_sales=net_sales,
        platform_fees=platform_fees,
        gmv_ads_settlement=gmv_ads_settlement,
        other_adjustment=other_adjustment,
        net_settlement=net_settlement,
        cogs=cogs,
        settlement_profit=settlement_profit,
        ads=external_ads,
        total_ads=total_ads,
        rough_profit=rough_profit,
        comm_pct=comm_pct,
        sales_commission=sales_commission,
        fixed_costs=fixed_costs,
        overhead_per_unit=overhead_per_unit,
        gross_profit=gross_profit,
        variable_costs=variable,
        contribution_margin=contribution,
        net_profit=net_profit,
        gross_margin_pct=_pct(gross_profit, net_sales),
        net_margin_pct=_pct(net_profit, net_sales),
        cm_ratio=cm_ratio,
        break_even_sales=bep,
        orders=int(sold["order_id"].nunique()),
        units=units,
        losing_orders_count=int(len(neg_orders)),
        losing_orders_loss=float(neg_orders["profit"].sum()) if not neg_orders.empty else 0.0,
        customer_payment=float(o["customer_payment"].sum()),
        platform_discount=float(o["platform_discount"].sum()),
        order_only_profit=order_only_profit,
    )


def cost_breakdown(
    result: PipelineResult,
    ads: float,
    sales_commission: float = 0.0,
    fixed_costs: float = 0.0,
) -> pd.DataFrame:
    """แจกแจงสัดส่วนค่าใช้จ่ายตามหมวดหมู่จริงของ TikTok Shop และบริษัท"""
    o = ensure_order_columns(result.orders)
    other_tiktok_fees = float((o["credit_card_fee"] + o["infra_and_other_fee"]).sum())
    # กรณี Snapshot เก่าที่ไม่ได้แยกย่อย growth/campaign ให้เก็บส่วนต่างที่เหลือมารวมไว้ไม่ให้ยอดตกหล่น
    categorized_fees = float(
        (
            o["tiktok_commission"]
            + o["order_fee"]
            + o["growth_fee"]
            + o["affiliate"]
            + o["campaign_service_fee"]
            + o["shipping"]
            + o["gmv_max_order_fee"]
        ).sum()
    ) + other_tiktok_fees
    residual_fee = max(0.0, float(o["platform_fees"].sum()) - categorized_fees)

    rows = [
        ("ต้นทุนสินค้า (ราคาทุน SKU)", float(o["cogs"].sum())),
        ("ค่าคอมมิชชั่น TikTok Shop", float(o["tiktok_commission"].sum())),
        ("ค่าธรรมเนียมคำสั่งซื้อ", float(o["order_fee"].sum())),
        ("ค่าธรรมเนียมสนับสนุนการเติบโตของร้านค้า", float(o["growth_fee"].sum())),
        ("ค่าคอมมิชชั่นแอฟฟิลิเอต", float(o["affiliate"].sum())),
        ("ค่าบริการคูปอง/แคมเปญ (ไลฟ์คุ้ม/Xtra/SFP)", float(o["campaign_service_fee"].sum())),
        ("ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง", float(o["shipping"].sum())),
        ("ค่าธรรมเนียมโครงสร้างพื้นฐาน/อื่นๆ", other_tiktok_fees + residual_fee),
        ("ค่าโฆษณา TikTok (หักด้วย GMV / GMV Max)", float(o["gmv_ads"].sum())),
        ("ค่าโฆษณาแคมเปญเพิ่มเติม (ชีต Ads)", float(ads)),
        ("ค่าคอมมิชชั่นคนขาย", float(sales_commission)),
        ("ค่าใช้จ่ายโรงงานรายเดือน", float(fixed_costs)),
    ]
    df = pd.DataFrame(rows, columns=["รายการ", "จำนวนเงิน"])
    return df[df["จำนวนเงิน"].round(2) > 0].sort_values("จำนวนเงิน", ascending=False).reset_index(drop=True)


def tiktok_report_table(result: PipelineResult) -> pd.DataFrame:
    """สร้างตารางสรุปโครงสร้างตามชีต 'รายงาน' และ 'คำอธิบายค่าธรรมเนียม' ของ TikTok Shop ทุกบรรทัดที่มีข้อมูล"""
    o = ensure_order_columns(result.orders)
    fd = dict(result.fee_details) if result.fee_details else {}

    def val(col: str, fallback: float = 0.0) -> float:
        return float(fd.get(col, fallback))

    total_settle = val("ยอดการชำระเงินทั้งหมด", float(o["net_settlement"].sum()))
    total_rev = val("รายได้ทั้งหมด", float(o["net_sales"].sum()))
    gross_after = val("ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย", float(o["gross_sales"].sum()))
    gross_before = val("ยอดรวมค่าสินค้าก่อนหักส่วนลด", float(o["gross_sales_before_discount"].sum()))
    seller_disc = val("ส่วนลดจากร้านค้า", float(o["seller_discount"].sum()))
    ref_after = val("ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย", float(o["refunds"].sum()))
    ref_before = val("ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า", float(o["refunds_before_discount"].sum()))
    ref_disc = val("เงินคืนจากส่วนลดร้านค้า", float(o["refund_seller_discount"].sum()))
    total_fees = val("ค่าธรรมเนียมทั้งหมด", -float(o["platform_fees"].sum()))
    total_adj = val("จำนวนการปรับยอด", float(o["adjustment"].sum()))

    rows: list[tuple[str, str, float, str]] = [
        ("สรุปยอดโอน", "ยอดการชำระเงินทั้งหมด (คอลัมน์ F)", total_settle, FEE_DESCRIPTIONS["ยอดการชำระเงินทั้งหมด"]),
        ("1. รายได้ทั้งหมด", "รายได้ทั้งหมด", total_rev, FEE_DESCRIPTIONS["รายได้ทั้งหมด"]),
        ("1. รายได้ทั้งหมด", "  ↳ ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย", gross_after, FEE_DESCRIPTIONS["ยอดรวมค่าสินค้าหลังหักส่วนลดจากผู้ขาย"]),
    ]
    if abs(gross_before) > 0 or abs(seller_disc) > 0:
        rows.append(("1. รายได้ทั้งหมด", "      • ยอดรวมค่าสินค้าก่อนหักส่วนลด", gross_before, FEE_DESCRIPTIONS["ยอดรวมค่าสินค้าก่อนหักส่วนลด"]))
        rows.append(("1. รายได้ทั้งหมด", "      • ส่วนลดจากร้านค้า", seller_disc, FEE_DESCRIPTIONS["ส่วนลดจากร้านค้า"]))

    rows.append(("1. รายได้ทั้งหมด", "  ↳ ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย", ref_after, FEE_DESCRIPTIONS["ยอดรวมเงินคืนหลังหักส่วนลดจากผู้ขาย"]))
    if abs(ref_before) > 0 or abs(ref_disc) > 0:
        rows.append(("1. รายได้ทั้งหมด", "      • ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า", ref_before, FEE_DESCRIPTIONS["ยอดรวมเงินคืนก่อนหักส่วนลดจากร้านค้า"]))
        rows.append(("1. รายได้ทั้งหมด", "      • เงินคืนจากส่วนลดร้านค้า", ref_disc, FEE_DESCRIPTIONS["เงินคืนจากส่วนลดร้านค้า"]))

    # 2. ค่าธรรมเนียมทั้งหมด (แสดงทุกตัวที่มียอดเกิดขึ้นจริงตามลำดับในชีต 'รายงาน')
    rows.append(("2. ค่าธรรมเนียมทั้งหมด", "ค่าธรรมเนียมทั้งหมด", total_fees, FEE_DESCRIPTIONS["ค่าธรรมเนียมทั้งหมด"]))
    for fee_col in SETTLEMENT_FEE_TOP_COLS:
        f_val = val(fee_col, 0.0)
        if abs(f_val) > 1e-9:
            rows.append(("2. ค่าธรรมเนียมทั้งหมด", f"  ↳ {fee_col}", f_val, FEE_DESCRIPTIONS.get(fee_col, "")))
            if fee_col == "ยอดรวมค่าจัดส่งที่ร้านค้าจ่ายจริง":
                for sub_c in SETTLEMENT_SHIPPING_SUB_COLS:
                    sv = val(sub_c, 0.0)
                    if abs(sv) > 1e-9:
                        rows.append(("2. ค่าธรรมเนียมทั้งหมด", f"      • {sub_c}", sv, "รายละเอียดประกอบค่าจัดส่ง"))
            elif fee_col in ("ค่าคอมมิชชั่นแอฟฟิลิเอต", "ค่าคอมมิชชั่นแอฟฟิลิเอตสำหรับโฆษณาร้านค้า"):
                sub_targets = (
                    SETTLEMENT_AFFILIATE_SUB_COLS[:2]
                    if fee_col == "ค่าคอมมิชชั่นแอฟฟิลิเอต"
                    else SETTLEMENT_AFFILIATE_SUB_COLS[2:]
                )
                for sub_c in sub_targets:
                    sv = val(sub_c, 0.0)
                    if abs(sv) > 1e-9:
                        rows.append(("2. ค่าธรรมเนียมทั้งหมด", f"      • {sub_c}", sv, "รายละเอียดก่อน/หลังหักภาษี ณ ที่จ่าย"))

    # 3. การปรับยอด (แยกตามประเภทธุรกรรม เช่น การชำระเงินด้วย GMV สำหรับโฆษณา TikTok, เงินชดเชยโลจิสติกส์ ฯลฯ)
    rows.append(("3. การปรับยอด", "จำนวนการปรับยอดรวม", total_adj, FEE_DESCRIPTIONS["จำนวนการปรับยอด"]))
    adj_keys = [k for k in fd.keys() if k.startswith("adj::")]
    if adj_keys:
        for k in sorted(adj_keys, key=lambda x: fd[x]):
            txn_label = k.split("adj::", 1)[1]
            rows.append(("3. การปรับยอด", f"  ↳ {txn_label}", float(fd[k]), FEE_DESCRIPTIONS.get(txn_label, "รายการปรับยอด")))
    elif abs(total_adj) > 1e-9:
        gmv_ded = -float(o["gmv_ads_deduction"].sum())
        other_adj = float(o["other_adjustment"].sum())
        if abs(gmv_ded) > 1e-9:
            rows.append(("3. การปรับยอด", "  ↳ การชำระเงินด้วย GMV สำหรับโฆษณา TikTok", gmv_ded, FEE_DESCRIPTIONS["การชำระเงินด้วย GMV สำหรับโฆษณา TikTok"]))
        if abs(other_adj) > 1e-9:
            rows.append(("3. การปรับยอด", "  ↳ การปรับยอดอื่น ๆ / เงินชดเชย", other_adj, "รายการปรับยอดอื่น ๆ"))

    # 4. ต้นทุนและกำไรของบริษัท (คอลัมน์ G และ H ในชีตรายละเอียดคำสั่งซื้อ)
    cogs_val = float(o["cogs"].sum())
    settle_profit = total_settle - cogs_val
    rows.append(("4. ต้นทุนและกำไร (บริษัท)", "ต้นทุนสินค้ารวม (คอลัมน์ G = SUMIFS มูลค่าจาก Order)", -cogs_val, "ผลรวม ราคาต่อหน่วย × จำนวนขายสุทธิ จากชีต Order"))
    rows.append(("4. ต้นทุนและกำไร (บริษัท)", "กำไรหลังหักต้นทุนสินค้า (คอลัมน์ H = F - G)", settle_profit, "ยอดการชำระเงินทั้งหมด − ต้นทุนสินค้ารวม"))

    # 5. ข้อมูลสนับสนุนเพิ่มเติม
    for extra_c in (
        "การชำระเงินของลูกค้า",
        "การคืนเงินจากลูกค้า",
        "ส่วนลดจากแพลตฟอร์ม",
        "การคืนเงินส่วนลดจากแพลตฟอร์ม",
        "คูปองส่วนลดร่วมของผู้ขาย",
        "การคืนเงินคูปองส่วนลดร่วมของผู้ขาย",
        "คูปองส่วนลดร่วมของแพลตฟอร์ม",
        "การคืนเงินคูปองส่วนลดร่วมของแพลตฟอร์ม",
        "ส่วนลดค่าจัดส่งจากร้านค้า",
    ):
        ev = val(extra_c, 0.0)
        if abs(ev) > 1e-9:
            rows.append(("5. ข้อมูลสนับสนุนเพิ่มเติม", extra_c, ev, FEE_DESCRIPTIONS.get(extra_c, "ข้อมูลสนับสนุนจาก TikTok Shop")))

    return pd.DataFrame(rows, columns=["หมวด", "รายการ", "จำนวนเงิน (บาท)", "คำอธิบาย"])


def by_category(result: PipelineResult) -> pd.DataFrame:
    o = ensure_order_columns(result.orders)
    sold_orders = o[o["txn_type"] == "คำสั่งซื้อ"]
    if sold_orders.empty:
        sold_orders = o
    g = (
        sold_orders.groupby("category")
        .agg(
            orders=("order_id", "nunique"),
            net_sales=("net_sales", "sum"),
            fees=("platform_fees", "sum"),
            net_settlement=("net_settlement", "sum"),
            cogs=("cogs", "sum"),
            profit=("profit", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "category": "หมวดหมู่",
                "orders": "ออเดอร์",
                "net_sales": "รายได้ทั้งหมด",
                "fees": "ค่าธรรมเนียมทั้งหมด",
                "net_settlement": "ยอดการชำระเงินทั้งหมด",
                "cogs": "ต้นทุนสินค้า",
                "profit": "กำไร",
            }
        )
    )
    g["Margin %"] = _pct_col(g["กำไร"], g["รายได้ทั้งหมด"])
    return g.sort_values("กำไร", ascending=False).reset_index(drop=True)


def by_sku(result: PipelineResult) -> pd.DataFrame:
    """สรุปกำไร/ขาดทุนรายสินค้า (SKU) ตามคอลัมน์ ราคาต่อหน่วย (I), มูลค่า (J) และยอดการชำระเงินทั้งหมด"""
    lines = result.order_lines
    if lines.empty:
        return pd.DataFrame()
    sold = lines[~lines["is_cancelled"]].copy()
    if sold.empty:
        return pd.DataFrame()
    if "Sku Quantity of return" not in sold.columns:
        sold["Sku Quantity of return"] = 0.0

    o = ensure_order_columns(result.orders)
    ord_pay = (
        o[o["txn_type"] == "คำสั่งซื้อ"]
        .groupby("order_id", as_index=False)["net_settlement"]
        .sum()
        .rename(columns={"order_id": "Order ID", "net_settlement": "_ord_payout"})
    )
    sold = sold.merge(ord_pay, on="Order ID", how="left")
    qty_denom = pd.to_numeric(sold.get("Quantity", 0.0), errors="coerce").fillna(0.0)
    keep_ratio = (sold["net_qty"] / qty_denom.where(qty_denom > 0, 1.0)).clip(lower=0.0, upper=1.0)
    keep_ratio = keep_ratio.where(qty_denom > 0, 1.0)
    sold["_eff_sales"] = sold["SKU Subtotal After Discount"] * keep_ratio

    ord_eff_sum = sold.groupby("Order ID")["_eff_sales"].transform("sum")
    ord_raw_sum = sold.groupby("Order ID")["SKU Subtotal After Discount"].transform("sum")
    ord_cnt = sold.groupby("Order ID")["Order ID"].transform("count")
    share = (sold["_eff_sales"] / ord_eff_sum.where(ord_eff_sum > 0)).fillna(
        (sold["SKU Subtotal After Discount"] / ord_raw_sum.where(ord_raw_sum > 0)).fillna(
            1.0 / ord_cnt.where(ord_cnt > 0, 1)
        )
    )
    sold["_alloc_payout"] = sold["_ord_payout"].where(sold["_ord_payout"].notna(), sold["_eff_sales"]) * share

    clean_sku = sold["Seller SKU"].fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
    clean_pname = sold["product_name"].fillna("").astype(str).str.strip()
    sold["_sku_disp"] = clean_sku.where(clean_sku != "", "(ไม่ระบุ SKU)")
    sold["_sku_grp"] = clean_sku.where(clean_sku != "", "__NOSKU__::" + clean_pname)

    g = (
        sold.groupby("_sku_grp", dropna=False)
        .agg(
            sku=("_sku_disp", "first"),
            name=("product_name", "first"),
            category=("category", "first"),
            unit_cost=("unit_cost", "first"),
            qty=("net_qty", "sum"),
            returned=("Sku Quantity of return", "sum"),
            sales=("_eff_sales", "sum"),
            payout=("_alloc_payout", "sum"),
            cogs=("line_cost", "sum"),
        )
        .reset_index(drop=True)
        .rename(
            columns={
                "sku": "SKU",
                "name": "ชื่อสินค้า",
                "category": "หมวดหมู่",
                "unit_cost": "ราคาทุน/หน่วย",
                "qty": "จำนวนขาย",
                "returned": "จำนวนคืน",
                "sales": "ยอดขายหลังส่วนลด",
                "payout": "ยอดการชำระเงินทั้งหมด",
                "cogs": "มูลค่าต้นทุน",
            }
        )
    )
    g["กำไรขั้นต้น"] = g["ยอดการชำระเงินทั้งหมด"] - g["มูลค่าต้นทุน"]
    g["สถานะ"] = g["กำไรขั้นต้น"].apply(lambda v: "❌ ขาดทุน" if v < 0 else "✅ กำไร")
    g["Margin %"] = _pct_col(g["กำไรขั้นต้น"], g["ยอดขายหลังส่วนลด"])

    total = g["จำนวนขาย"] + g["จำนวนคืน"]
    g["อัตราคืน %"] = (g["จำนวนคืน"] / total.where(total > 0) * 100).fillna(0)
    return g.sort_values("กำไรขั้นต้น", ascending=True).reset_index(drop=True)


def daily_trend(result: PipelineResult) -> pd.DataFrame:
    """สรุปแนวโน้มรายวัน: รายได้, ยอดชำระ F, ต้นทุน G, กำไรก่อนแอด GMV, ค่าแอด GMV และกำไรสุทธิ H"""
    o = ensure_order_columns(result.orders).dropna(subset=["date"])
    if o.empty:
        return pd.DataFrame()
    d = o.assign(day=pd.to_datetime(o["date"]).dt.date)

    sold_orders = d[d["txn_type"] == "คำสั่งซื้อ"]
    ord_cnt = sold_orders.groupby("day")["order_id"].nunique().rename("orders")
    ord_profit = sold_orders.groupby("day")["profit"].sum().rename("order_profit")

    g = (
        d.groupby("day")
        .agg(
            net_sales=("net_sales", "sum"),
            net_settlement=("net_settlement", "sum"),
            cogs=("cogs", "sum"),
            gmv_ads=("gmv_ads_deduction", "sum"),
            profit=("profit", "sum"),
        )
        .join(ord_cnt, how="left")
        .join(ord_profit, how="left")
        .fillna({"orders": 0, "order_profit": 0.0})
        .reset_index()
    )
    g["orders"] = g["orders"].astype(int)
    return g.rename(
        columns={
            "day": "วันที่",
            "net_sales": "รายได้ทั้งหมด",
            "net_settlement": "ยอดการชำระเงินทั้งหมด (F)",
            "cogs": "ต้นทุนรวม (G)",
            "gmv_ads": "โฆษณา GMV",
            "order_profit": "กำไรเฉพาะคำสั่งซื้อ",
            "profit": "กำไร",
            "orders": "ออเดอร์",
        }
    )


def monthly_comparison_table(rows: list[tuple[str, Summary]]) -> pd.DataFrame:
    """สร้างตารางเปรียบเทียบผลประกอบการแยกตามแต่ละงวดเดือน (พร้อมคำนวณ Margin %)"""
    if not rows:
        return pd.DataFrame()
    has_ext_ads = any(s.ads > 0 for _, s in rows)
    records: list[dict] = []
    for label, s in rows:
        rec: dict = {
            "งวดเดือน": label,
            "ออเดอร์": int(s.orders),
            "จำนวนชิ้น": float(s.units),
            "รายได้ทั้งหมด": round(s.net_sales, 2),
            "ค่าธรรมเนียมทั้งหมด": round(s.platform_fees, 2),
            "โฆษณา GMV (หักใน F)": round(s.gmv_ads_settlement, 2),
            "ยอดการชำระเงินทั้งหมด (F)": round(s.net_settlement, 2),
            "ต้นทุนรวม (G)": round(s.cogs, 2),
        }
        if has_ext_ads:
            rec["ค่าแอดแยกชีต (Ads)"] = round(s.ads, 2)
        rec.update(
            {
                "กำไรจากการขาย": round(s.rough_profit, 2),
                "ค่าคอมฯ & รายเดือน": round(s.sales_commission + s.fixed_costs, 2),
                "กำไรสุทธิสุดท้าย": round(s.net_profit, 2),
                "Net Margin %": round(s.net_margin_pct, 2),
            }
        )
        records.append(rec)
    return pd.DataFrame(records)


def calendar_monthly_trend(result: PipelineResult) -> pd.DataFrame:
    """สรุปยอดแยกตามเดือนปฏิทิน YYYY-MM จากแถวคำสั่งซื้อจริง (ใช้ได้แม้โยนรวมมาในไฟล์เดียว)"""
    o = ensure_order_columns(result.orders)
    if o.empty:
        return pd.DataFrame()
    dt = pd.to_datetime(o["date"], errors="coerce")
    if "created_date" in o.columns:
        dt = dt.fillna(pd.to_datetime(o["created_date"], errors="coerce"))
    valid = o[dt.notna()].copy()
    if valid.empty:
        return pd.DataFrame()
    valid["ym"] = dt[dt.notna()].dt.to_period("M").astype(str)

    sold_cnt = (
        valid[valid["txn_type"] == "คำสั่งซื้อ"]
        .groupby("ym")["order_id"]
        .nunique()
        .rename("orders")
    )
    g = (
        valid.groupby("ym")
        .agg(
            units=("units", "sum"),
            net_sales=("net_sales", "sum"),
            platform_fees=("platform_fees", "sum"),
            gmv_ads=("gmv_ads_deduction", "sum"),
            net_settlement=("net_settlement", "sum"),
            cogs=("cogs", "sum"),
            profit=("profit", "sum"),
        )
        .join(sold_cnt, how="left")
        .fillna({"orders": 0})
        .reset_index()
        .sort_values("ym")
    )
    g["orders"] = g["orders"].astype(int)
    g["Margin %"] = _pct_col(g["profit"], g["net_sales"]).round(2)
    return g.rename(
        columns={
            "ym": "เดือนปฏิทิน",
            "orders": "ออเดอร์",
            "units": "จำนวนชิ้น",
            "net_sales": "รายได้ทั้งหมด",
            "platform_fees": "ค่าธรรมเนียมทั้งหมด",
            "gmv_ads": "โฆษณา GMV",
            "net_settlement": "ยอดการชำระเงินทั้งหมด (F)",
            "cogs": "ต้นทุนรวม (G)",
            "profit": "กำไร (H = F − G)",
        }
    )


# ---------------- What-If Simulator ----------------
@dataclass
class WhatIf:
    net_sales: float
    variable_costs: float
    net_profit: float
    profit_change: float
    volume_needed_pct: float | None
    break_even_sales: float | None


def what_if(
    base: Summary,
    price_pct: float = 0,
    cost_pct: float = 0,
    volume_pct: float = 0,
    ads_pct: float = 0,
) -> WhatIf:
    p, c, v, a = price_pct / 100, cost_pct / 100, volume_pct / 100, ads_pct / 100
    fees_ratio = base.platform_fees / base.net_sales if base.net_sales else 0.0

    unit_sales = base.net_sales * (1 + p)
    unit_fees = (unit_sales * fees_ratio) if base.net_sales else base.platform_fees
    unit_cm = unit_sales - unit_fees + base.other_adjustment - base.cogs * (1 + c)
    sim_total_ads = (base.gmv_ads_settlement + base.ads) * (1 + a)

    net_sales = unit_sales * (1 + v)
    sim_fees = (net_sales * fees_ratio) if base.net_sales else base.platform_fees * (1 + v)
    variable = sim_fees + base.cogs * (1 + c) * (1 + v) + sim_total_ads
    rough_sim = unit_cm * (1 + v) - sim_total_ads

    if p == 0 and c == 0 and v == 0 and a == 0:
        comm_sim = base.sales_commission
    elif base.sales_commission > 0 and base.rough_profit > 0:
        eff_comm_rate = base.sales_commission / base.rough_profit
        comm_sim = max(0.0, rough_sim * eff_comm_rate)
    elif base.comm_pct > 0:
        if base.sales_commission > 0:
            comm_sim = max(0.0, base.sales_commission + (rough_sim - base.rough_profit) * (base.comm_pct / 100.0))
        else:
            comm_sim = max(0.0, rough_sim * (base.comm_pct / 100.0))
    else:
        comm_sim = 0.0

    net_profit = rough_sim - comm_sim - base.fixed_costs

    target = base.net_profit + comm_sim + sim_total_ads + base.fixed_costs
    volume_needed = (target / unit_cm - 1) * 100 if unit_cm > 0 else None

    cm_ratio = (net_sales - variable - comm_sim) / net_sales if net_sales else 0
    bep = (
        base.fixed_costs / cm_ratio
        if (cm_ratio > 0 and base.fixed_costs > 0)
        else (0.0 if base.fixed_costs == 0 and cm_ratio > 0 else None)
    )
    return WhatIf(net_sales, variable + comm_sim, net_profit, net_profit - base.net_profit, volume_needed, bep)


# ---------------- Loss & Anomaly Detection ----------------
def detect_anomalies(
    result: PipelineResult,
    fee_ratio_limit: float = 40.0,
    refund_rate_limit: float = 20.0,
) -> dict[str, pd.DataFrame]:
    o = ensure_order_columns(result.orders)
    o = o[o["txn_type"] == "คำสั่งซื้อ"].copy()
    o["fee_ratio_%"] = (o["platform_fees"] / o["net_sales"].where(o["net_sales"] > 0) * 100).fillna(0)

    known_cost = o[~o["cost_missing"]]
    negative = known_cost[(known_cost["profit"] < 0) & (known_cost["net_sales"] > 0)]
    high_fee = o[(o["fee_ratio_%"] > fee_ratio_limit) & (o["net_sales"] > 0)]
    refunded = o[(o["refunds"] < 0) & (o["net_sales"] <= 0) & (o["platform_fees"] > 0)]

    sku = by_sku(result)
    high_refund = sku[(sku["อัตราคืน %"] > refund_rate_limit) & (sku["จำนวนคืน"] >= 3)] if not sku.empty else sku

    show = ["order_id", "date", "category", "net_sales", "platform_fees", "fee_ratio_%", "net_settlement", "cogs", "profit"]
    return {
        "negative_profit": negative[show].sort_values("profit"),
        "high_fee": high_fee[show].sort_values("fee_ratio_%", ascending=False),
        "refund_with_fee": refunded[show].sort_values("platform_fees", ascending=False),
        "high_refund_sku": high_refund,
        "missing_cost": result.missing_skus,
    }
