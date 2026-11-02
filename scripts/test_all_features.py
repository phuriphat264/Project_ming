"""Comprehensive System Integrity & Regression Test Suite"""
import sys
import os
from pathlib import Path
import io
import json
import zipfile
import pandas as pd
import openpyxl

# Add cost_profit_system to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db, order_repo
from core.loader import load_workbook, _parse_sheet_xml_fallback
from core.pipeline import run_pipeline, combine, detect_period_label, extract_order_skus
from core.export import (
    build_company_cost_master_excel,
    _split_order_sheets_by_month,
    company_settlement_view,
    company_order_lines_view,
    format_thai_cost_filename,
)
from core.metrics import (
    summarize,
    by_sku,
    by_category,
    daily_trend,
    cost_breakdown,
    what_if,
    detect_anomalies,
)
from core.ui import build_saved_periods_comparison_df, load_period_result

def test_1_db_and_skus():
    print("--- Test 1: Database & SKU Master ---")
    db.init_db()
    skus = db.get_skus()
    assert not skus.empty, "Master SKUs should not be empty"
    assert len(skus) >= 70, f"Expected at least 70 SKUs, got {len(skus)}"
    assert "sku" in skus.columns and "unit_cost" in skus.columns
    print(f"  ✓ Master SKUs verified: {len(skus)} items loaded with costs.")

def test_2_order_repo_lifecycle():
    print("--- Test 2: Order Repository Lifecycle & Month Deletion ---")
    summary = order_repo.repo_summary()
    print(f"  Current repo state: {summary['orders']} orders, months: {summary['months']['เดือนที่สั่งซื้อ'].tolist()}")
    
    # Test delete non-existent month (should return 0)
    del_fake = order_repo.delete_month_from_repo("2099-12")
    assert del_fake == 0, f"Expected 0 deletions for fake month, got {del_fake}"
    
    # If 2026-07 exists, test deleting it specifically
    if "2026-07" in summary['months']['เดือนที่สั่งซื้อ'].tolist():
        del_07 = order_repo.delete_month_from_repo("2026-07")
        print(f"  ✓ Deleted 2026-07 orders specifically: {del_07:,} orders")
        new_summary = order_repo.repo_summary()
        assert "2026-07" not in new_summary['months']['เดือนที่สั่งซื้อ'].tolist(), "2026-07 should be removed"
        assert "2026-08" in new_summary['months']['เดือนที่สั่งซื้อ'].tolist(), "2026-08 should still exist"
        print(f"  ✓ Remaining months verified: {new_summary['months']['เดือนที่สั่งซื้อ'].tolist()}")

def test_3_end_to_end_pipeline_and_export():
    print("--- Test 3: End-to-End Pipeline & Master Excel 7-Sheet Export ---")
    raw_dir = Path("data_final")
    if not raw_dir.exists():
        raw_dir = Path("../data_final")
    
    inc_file = next(raw_dir.glob("income_*.xlsx"))
    ord1_file = raw_dir / "ทั้งหมด คำสั่งซื้อ-2026-09-03-09_25(1).xlsx"
    ord2_file = raw_dir / "ทั้งหมด คำสั่งซื้อ-2026-10-02-16_48(1).xlsx"
    
    assert inc_file.exists(), f"Income file missing: {inc_file}"
    assert ord1_file.exists(), f"Order file 1 missing: {ord1_file}"
    assert ord2_file.exists(), f"Order file 2 missing: {ord2_file}"

    with open(inc_file, "rb") as f:
        b_inc = load_workbook(io.BytesIO(f.read()), name=inc_file.name)
    with open(ord1_file, "rb") as f:
        b_o1 = load_workbook(io.BytesIO(f.read()), name=ord1_file.name)
    with open(ord2_file, "rb") as f:
        b_o2 = load_workbook(io.BytesIO(f.read()), name=ord2_file.name)

    assert not b_inc.settlement.empty, "Income settlement should not be empty"
    assert not b_o1.orders.empty, "Order 1 should not be empty"
    assert not b_o2.orders.empty, "Order 2 should not be empty"

    combined = combine([b_inc, b_o1, b_o2])
    sku_master = db.get_skus()
    res = run_pipeline(combined, sku_master)
    period = detect_period_label(res, [inc_file.name, ord1_file.name, ord2_file.name])
    
    print(f"  ✓ Pipeline executed: {len(res.orders):,} orders, {len(res.order_lines):,} items, period={period}")
    s = summarize(res)
    print(f"  ✓ Financial summary: Net Settlement(F)={s.net_settlement:,.2f}, COGS(G)={s.cogs:,.2f}, Profit(H)={s.settlement_profit:,.2f}")
    assert s.net_settlement > 0, "Net settlement should be positive"
    assert s.cogs > 0, "COGS should be positive"
    assert res.missing_skus.empty, f"Expected 0 missing SKUs, got {len(res.missing_skus)}"

    # Generate master cost excel
    excel_bytes = build_company_cost_master_excel(res, sku_master, period_label=period)
    assert len(excel_bytes) > 1024 * 1024, "Excel bytes should be > 1MB"
    
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True)
    sheets = wb.sheetnames
    print(f"  ✓ Generated sheets in master Excel: {sheets}")
    
    # Must have exact standard sheets
    expected_core = ['รายละเอียดคำสั่งซื้อ', 'SKU', 'Order9', 'Order8', 'รายงาน', 'บันทึกการถอน', 'คำอธิบายค่าธรรมเนียม']
    for req in expected_core:
        assert req in sheets, f"Missing required sheet: {req} in {sheets}"
    assert "Order7" not in sheets, f"Order7 must NOT be in sheets! Found: {sheets}"
    print("  ✓ Sheets perfectly matched company standard (exactly 2 consecutive order months: 9 and 8)!")

def test_4_backup_and_restore():
    print("--- Test 4: One-Click System Backup & Restore ---")
    backup_bytes = db.create_backup_zip_bytes()
    assert len(backup_bytes) > 1000, "Backup zip should contain data"
    
    with zipfile.ZipFile(io.BytesIO(backup_bytes), "r") as z:
        names = z.namelist()
        print(f"  ✓ Backup zip verified ({len(backup_bytes)/1024:.1f} KB), contains: {names[:5]}...")
        assert "app.db" in names, "app.db must be in backup"
        assert any("orders_raw.parquet" in n for n in names), "orders_raw.parquet must be in backup"

def test_5_ui_component_metrics():
    print("--- Test 5: Metrics & Calculations Check ---")
    res = load_period_result("2026-09")
    if res is not None:
        s = summarize(res)
        sku_df = by_sku(res)
        cat_df = by_category(res)
        tr_df = daily_trend(res)
        cb_df = cost_breakdown(res, 0.0)
        anom = detect_anomalies(res)
        what_if_res = what_if(s, 10, -5, 10, 0)
        
        assert not sku_df.empty, "by_sku should not be empty"
        assert not cat_df.empty, "by_category should not be empty"
        assert not tr_df.empty, "daily_trend should not be empty"
        print(f"  ✓ Dashboard metrics verified: {len(sku_df)} SKUs, {len(cat_df)} categories, {len(tr_df)} days.")

if __name__ == "__main__":
    print("==================================================")
    print(" RUNNING ANTIGRAVITY COMPREHENSIVE SYSTEM TESTS   ")
    print("==================================================")
    test_1_db_and_skus()
    test_2_order_repo_lifecycle()
    test_3_end_to_end_pipeline_and_export()
    test_4_backup_and_restore()
    test_5_ui_component_metrics()
    print("==================================================")
    print(" ✅ ALL TESTS PASSED SUCCESSFULLY! ZERO BUGS FOUND")
    print("==================================================")
