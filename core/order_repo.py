"""คลังคำสั่งซื้อสะสม (Order Repository)

เก็บแถวคำสั่งซื้อดิบ (ชีต Order / OrderSKUList) ทุกเดือนที่เคยนำเข้าไว้ในไฟล์ Parquet ไฟล์เดียว
เพื่อให้รอบถัดไปอัปโหลดเฉพาะไฟล์ Order เดือนล่าสุด 1 ไฟล์ได้ แล้วระบบดึงออเดอร์เดือนก่อน
(ที่เงินเพิ่งเข้าในรอบ Income ใหม่) จากคลังมาจับคู่ต้นทุนให้อัตโนมัติ

- รอบแรก: นำเข้า Income + ไฟล์ Order 2 เดือน (เช่น Order8 + Order9) → บันทึกทั้งสองเดือนลงคลัง
- รอบถัดไป: นำเข้า Income + ไฟล์ Order เดือนใหม่ 1 ไฟล์ (เช่น Order10) → ดึง Order9 จากคลังให้เอง
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .db import DB_PATH
from .loader import ORDER_KEY, SETTLEMENT_KEY, LoadedWorkbook, orders_from_raw

REPO_PATH = DB_PATH.parent / "order_repo" / "orders_raw.parquet"
CREATED_COL = "Created Time"


def _repo_path(db_path: Path | None = None, shop_code: str | None = None) -> Path:
    base_dir = (db_path.parent if db_path else DB_PATH.parent) / "order_repo"
    if shop_code and str(shop_code).strip().lower() not in ("matang", "all", ""):
        return base_dir / f"orders_raw_{str(shop_code).strip().lower()}.parquet"
    p_matang = base_dir / "orders_raw_matang.parquet"
    if p_matang.exists():
        return p_matang
    return base_dir / "orders_raw.parquet"


def _normalize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """เก็บเฉพาะแถวที่เป็นคำสั่งซื้อจริง (ตัดแถวคำอธิบายภาษาอังกฤษ) และแปลงทุกคอลัมน์เป็นข้อความ"""
    if raw is None or raw.empty or ORDER_KEY not in raw.columns:
        return pd.DataFrame()
    df = raw.copy()
    df = df.loc[:, ~df.columns.duplicated()]
    df[ORDER_KEY] = df[ORDER_KEY].astype(str).str.strip()
    df = df[df[ORDER_KEY].str.fullmatch(r"\d+")]
    for c in df.columns:
        df[c] = df[c].where(df[c].isna(), df[c].astype(str))
    return df.drop_duplicates().reset_index(drop=True)


def load_repo(db_path: Path | None = None, shop_code: str | None = None) -> pd.DataFrame:
    p = _repo_path(db_path, shop_code=shop_code)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def save_to_repo(raw_orders: pd.DataFrame, db_path: Path | None = None, shop_code: str | None = None) -> dict[str, int]:
    """บันทึกแถวคำสั่งซื้อลงคลัง — ถ้า Order ID ซ้ำกับที่มีอยู่ จะใช้ข้อมูลชุดใหม่แทนทั้งออเดอร์ (สถานะล่าสุด)"""
    new = _normalize_raw(raw_orders)
    if new.empty:
        return {"added": 0, "replaced": 0, "total": repo_summary(db_path, shop_code=shop_code)["orders"]}

    repo = load_repo(db_path, shop_code=shop_code)
    new_ids = set(new[ORDER_KEY])
    if repo.empty:
        replaced = 0
        merged = new
    else:
        old_ids = set(repo[ORDER_KEY].astype(str))
        replaced = len(new_ids & old_ids)
        keep_old = repo[~repo[ORDER_KEY].astype(str).isin(new_ids)]
        merged = pd.concat([keep_old, new], ignore_index=True)
        for c in merged.columns:
            merged[c] = merged[c].where(merged[c].isna(), merged[c].astype(str))

    p = _repo_path(db_path, shop_code=shop_code)
    p.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(p, index=False)
    return {
        "added": len(new_ids) - replaced,
        "replaced": replaced,
        "total": int(merged[ORDER_KEY].nunique()),
    }


def _created_month(df: pd.DataFrame) -> pd.Series:
    if CREATED_COL not in df.columns:
        return pd.Series("ไม่ทราบเดือน", index=df.index)
    dt = pd.to_datetime(df[CREATED_COL], errors="coerce", format="mixed", dayfirst=True)
    return dt.dt.strftime("%Y-%m").fillna("ไม่ทราบเดือน")


_REPO_SUMMARY_CACHE: dict[str, tuple[float, dict]] = {}


def repo_summary(db_path: Path | None = None, shop_code: str | None = None) -> dict:
    """สรุปจำนวนออเดอร์ในคลัง แยกตามเดือนที่สร้างคำสั่งซื้อ (มีแคชตาม mtime รวดเร็วระดับเสี้ยววินาที)"""
    global _REPO_SUMMARY_CACHE
    p = _repo_path(db_path, shop_code=shop_code)
    cache_k = str(p)
    if not p.exists():
        return {"orders": 0, "lines": 0, "months": pd.DataFrame(columns=["เดือนที่สั่งซื้อ", "จำนวนออเดอร์", "จำนวนแถวสินค้า"])}
    mtime = p.stat().st_mtime
    if cache_k in _REPO_SUMMARY_CACHE and _REPO_SUMMARY_CACHE[cache_k][0] == mtime:
        return _REPO_SUMMARY_CACHE[cache_k][1]

    repo = load_repo(db_path, shop_code=shop_code)
    if repo.empty:
        res = {"orders": 0, "lines": 0, "months": pd.DataFrame(columns=["เดือนที่สั่งซื้อ", "จำนวนออเดอร์", "จำนวนแถวสินค้า"])}
    else:
        tmp = pd.DataFrame({"oid": repo[ORDER_KEY].astype(str), "month": _created_month(repo)})
        months = (
            tmp.groupby("month")
            .agg(orders=("oid", "nunique"), lines=("oid", "size"))
            .reset_index()
            .sort_values("month", ascending=False)
            .rename(columns={"month": "เดือนที่สั่งซื้อ", "orders": "จำนวนออเดอร์", "lines": "จำนวนแถวสินค้า"})
        )
        res = {"orders": int(tmp["oid"].nunique()), "lines": len(tmp), "months": months}
    _REPO_SUMMARY_CACHE[cache_k] = (mtime, res)
    return res


def clear_repo(db_path: Path | None = None, shop_code: str | None = None) -> None:
    global _REPO_SUMMARY_CACHE
    _REPO_SUMMARY_CACHE.clear()
    _repo_path(db_path, shop_code=shop_code).unlink(missing_ok=True)


def delete_month_from_repo(month: str, db_path: Path | None = None, shop_code: str | None = None) -> int:
    """ลบคำสั่งซื้อเฉพาะเดือนที่ระบุ (เช่น '2026-07') ออกจากคลังสะสม คืนค่าจำนวนออเดอร์ที่ถูกลบ"""
    global _REPO_SUMMARY_CACHE
    repo = load_repo(db_path, shop_code=shop_code)
    if repo.empty:
        return 0
    m_series = _created_month(repo)
    mask = m_series == month
    deleted_orders = int(repo.loc[mask, ORDER_KEY].nunique()) if mask.any() else 0
    if deleted_orders > 0:
        kept = repo[~mask].reset_index(drop=True)
        p = _repo_path(db_path, shop_code=shop_code)
        if kept.empty:
            p.unlink(missing_ok=True)
        else:
            kept.to_parquet(p, index=False)
        _REPO_SUMMARY_CACHE.clear()
    return deleted_orders


def pull_for_settlement(
    settlement_ids: set[str],
    exclude_ids: set[str],
    db_path: Path | None = None,
    shop_code: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ดึงแถวคำสั่งซื้อจากคลัง เฉพาะ Order ID ที่อยู่ใน Income แต่ไม่มีในไฟล์ Order ที่อัปโหลดรอบนี้

    คืนค่า (raw_rows, cleaned_orders) — raw ใช้ส่งออกชีต Order, cleaned ใช้คำนวณต้นทุน
    """
    repo = load_repo(db_path, shop_code=shop_code)
    if repo.empty or not settlement_ids:
        return pd.DataFrame(), pd.DataFrame()
    ids = repo[ORDER_KEY].astype(str)
    raw = repo[ids.isin(settlement_ids) & ~ids.isin(exclude_ids)].reset_index(drop=True)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    return raw, orders_from_raw(raw, sheet_label="คลังคำสั่งซื้อสะสม")


def attach_repo_orders(data: LoadedWorkbook, db_path: Path | None = None, shop_code: str | None = None) -> tuple[LoadedWorkbook, int]:
    """เติมคำสั่งซื้อเดือนก่อนจากคลัง เข้าไปในชุดข้อมูลที่จะคำนวณ (เฉพาะออเดอร์ที่ Income อ้างถึงแต่ยังไม่มีข้อมูล)

    คืนค่า (data, จำนวนออเดอร์ที่ดึงจากคลัง)
    """
    if data.settlement.empty or SETTLEMENT_KEY not in data.settlement.columns:
        return data, 0
    settle_ids = set(data.settlement[SETTLEMENT_KEY].astype(str).str.strip())
    have_ids = set(data.orders[ORDER_KEY].astype(str)) if not data.orders.empty else set()
    raw, cleaned = pull_for_settlement(settle_ids, have_ids, db_path, shop_code=shop_code)
    if cleaned.empty:
        return data, 0
    data.orders = pd.concat([data.orders, cleaned], ignore_index=True)
    data.raw_orders = pd.concat([data.raw_orders, raw], ignore_index=True)
    n = int(cleaned[ORDER_KEY].nunique())
    data.notes.append(f"ดึงคำสั่งซื้อเดือนก่อนจากคลังคำสั่งซื้อสะสม {n:,} ออเดอร์ ({len(cleaned):,} แถว)")
    return data, n
