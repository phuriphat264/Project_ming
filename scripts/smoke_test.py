"""ทดสอบ pipeline กับไฟล์ Excel จริงในโฟลเดอร์แม่ (ไม่แตะฐานข้อมูลจริง)

รัน:  .venv/bin/python scripts/smoke_test.py
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from core import db  # noqa: E402
from core.export import to_excel, to_html_report  # noqa: E402
from core.loader import load_workbook  # noqa: E402
from core.metrics import by_category, by_sku, detect_anomalies, summarize, what_if  # noqa: E402
from core.pipeline import combine, run_pipeline  # noqa: E402

files = sorted(ROOT.parent.glob("ต้นทุน*.xlsx"))
tmp_db = Path(tempfile.mkdtemp()) / "test.db"
db.init_db(tmp_db)
assert db.verify_user("admin", "admin123", tmp_db)["role"] == "admin"
assert db.verify_user("admin", "wrong", tmp_db) is None

for f in files:
    t = time.time()
    wb = load_workbook(str(f))
    data = combine([wb])
    print(f"\n=== {f.name}  (อ่าน {time.time() - t:.1f}s)")
    for n in wb.notes:
        print("   ", n)
    if data.settlement.empty and data.orders.empty:
        print("    (ไม่มีข้อมูลที่ใช้ได้ — ข้าม)")
        continue

    # จำลอง SKU master: ใส่ราคาทุน 30% ของราคาเต็ม เพื่อทดสอบการคำนวณ
    if not data.orders.empty:
        seen = data.orders.groupby("Seller SKU").agg(
            name=("Product Name", "first"), unit_cost=("SKU Unit Original Price", "max")).reset_index()
        seen = seen.rename(columns={"Seller SKU": "sku"})
        seen["unit_cost"] *= 0.3
        db.save_skus(seen, tmp_db)
    sku = db.get_skus(tmp_db)

    res = run_pipeline(data, sku)
    s = summarize(res, fixed_costs=50_000)
    for w in res.warnings:
        print("    ⚠", w)
    print(f"    source={res.source} rows={len(res.orders):,} orders={s.orders:,}")
    print(f"    net_sales={s.net_sales:,.2f} fees={s.platform_fees:,.2f} cogs={s.cogs:,.2f} "
          f"net_profit={s.net_profit:,.2f} margin={s.net_margin_pct:.1f}% BEP={s.break_even_sales}")

    # ตรวจความสอดคล้อง: กำไรสุทธิ = เงินที่ได้รับจริง − COGS − ads − fixed
    expect = res.orders["net_settlement"].sum() - s.cogs - s.ads - s.fixed_costs
    assert abs(expect - s.net_profit) < 0.01, (expect, s.net_profit)

    # เทียบกับยอดรวมคอลัมน์ "รายได้" ที่บริษัทคำนวณไว้ในไฟล์ (ถ้ามี)
    if res.source == "settlement" and "รายได้" in data.settlement.columns:
        excel_rev = pd.to_numeric(data.settlement["รายได้"], errors="coerce").sum()
        print(f"    ตรวจสอบกับ Excel: รายได้(ไฟล์)={excel_rev:,.2f}  ระบบ={res.orders['net_settlement'].sum():,.2f}")

    w0 = what_if(s)
    assert abs(w0.net_profit - s.net_profit) < 0.01 and abs(w0.volume_needed_pct or 0) < 1e-6
    w = what_if(s, price_pct=-15)
    print(f"    what-if ลดราคา 15%: กำไร {w.net_profit:,.0f}  ต้องขายเพิ่ม {w.volume_needed_pct}")

    a = detect_anomalies(res)
    print("    anomalies:", {k: len(v) for k, v in a.items()})
    by_category(res), by_sku(res)
    assert to_excel(s, {"orders": res.orders})[:2] == b"PK"
    assert "รายงาน" in to_html_report(s, "test", by_category(res), by_sku(res).head())

print("\n✅ smoke test ผ่านทั้งหมด")
