"""คลังคำสั่งซื้อสะสม (Order Repository) — แยกอิสระ 100% ตามช่องทางร้านค้า (Multi-Channel Isolated)

เก็บแถวคำสั่งซื้อดิบ (ชีต Order / OrderSKUList) ทุกเดือนที่เคยนำเข้าไว้ในไฟล์ Parquet แยกตามรหัสร้านค้า
(`orders_raw_<shop_code>.parquet`) เพื่อไม่ให้การเพิ่มหรือลบคลังของช่องทางหนึ่งกระทบกับช่องทางอื่นโดยเด็ดขาด
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import pandas as pd

from . import db
from .loader import ORDER_KEY, SETTLEMENT_KEY, LoadedWorkbook, load_workbook, orders_from_raw

REPO_PATH = db.DB_PATH.parent / "order_repo" / "orders_raw_matang.parquet"
CREATED_COL = "Created Time"
_MIGRATION_STATE_KEY = "order_repo_isolated_v3"

_REPO_SUMMARY_CACHE: dict[str, tuple[float, dict]] = {}
_MIGRATED_DBS: set[str] = set()
_MIGRATING_NOW: dict[str, bool] = {}


def reset_migration_cache() -> None:
    """ล้างสถานะแคชในหน่วยความจำ (ใช้หลังกู้คืนไฟล์ Backup .zip)"""
    _REPO_SUMMARY_CACHE.clear()
    _MIGRATED_DBS.clear()
    _MIGRATING_NOW.clear()


def normalize_shop_code(shop_code: str | None = None) -> str:
    """แปลงรหัสร้านค้าให้ปลอดภัยสำหรับตั้งชื่อไฟล์แยกเฉพาะร้าน 100%"""
    raw = str(shop_code or "").strip().lower()
    if not raw or raw in ("all", "none", "settlement", "orders_only"):
        return "matang"
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", raw).strip("_")
    return safe or "matang"


def _repo_path(db_path: Path | None = None, shop_code: str | None = None) -> Path:
    base_dir = (db_path.parent if db_path else db.DB_PATH.parent) / "order_repo"
    code = normalize_shop_code(shop_code)
    return base_dir / f"orders_raw_{code}.parquet"


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


def _load_repo_direct(db_path: Path | None = None, shop_code: str | None = None) -> pd.DataFrame:
    p = _repo_path(db_path, shop_code=shop_code)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _save_to_repo_direct(
    raw_orders: pd.DataFrame,
    db_path: Path | None = None,
    shop_code: str | None = None,
) -> dict[str, int]:
    new = _normalize_raw(raw_orders)
    p = _repo_path(db_path, shop_code=shop_code)
    if new.empty:
        existing = _load_repo_direct(db_path, shop_code=shop_code)
        tot = int(existing[ORDER_KEY].nunique()) if not existing.empty and ORDER_KEY in existing.columns else 0
        return {"added": 0, "replaced": 0, "total": tot}

    repo = _load_repo_direct(db_path, shop_code=shop_code)
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

    p.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(p, index=False)
    _REPO_SUMMARY_CACHE.pop(str(p), None)
    return {
        "added": len(new_ids) - replaced,
        "replaced": replaced,
        "total": int(merged[ORDER_KEY].nunique()),
    }


def can_rebuild_repo_for_shop(shop_code: str | None, db_path: Path | None = None) -> bool:
    """ตรวจสอบอย่างรวดเร็วว่ามีข้อมูลงวด (Snapshot) หรือไฟล์คำสั่งซื้อใน data/uploads/ ของช่องนี้ให้กู้คืนหรือไม่"""
    code = normalize_shop_code(shop_code)
    snaps = db.list_snapshots(shop_code=code, db_path=db_path)
    if not snaps.empty:
        for m in snaps["month"].tolist():
            loaded = db.load_snapshot(str(m), db_path=db_path, shop_code=code)
            if loaded is not None:
                ro = loaded.get("raw_orders")
                ln = loaded.get("lines")
                if (ro is not None and not ro.empty) or (ln is not None and not ln.empty and ORDER_KEY in ln.columns):
                    return True
    ups = db.list_uploaded_excels(db_path=db_path, shop_code=code)
    if not ups.empty:
        non_inc = ups[~ups["original_name"].astype(str).str.lower().str.startswith("income")]
        if not non_inc.empty:
            return True
    return False


def rebuild_repo_for_shop(
    shop_code: str | None,
    db_path: Path | None = None,
    include_uploads: bool = True,
) -> dict[str, int]:
    """กู้คืน/สร้างคลังคำสั่งซื้อสะสมเฉพาะของช่องที่ระบุ จาก Snapshot และไฟล์ Excel ที่เคยอัปโหลดไว้"""
    code = normalize_shop_code(shop_code)
    frames: list[pd.DataFrame] = []

    # 1. ดึงจากไฟล์ Parquet ของงวดที่บันทึกไว้ (รวดเร็วระดับเสี้ยววินาที)
    snaps = db.list_snapshots(shop_code=code, db_path=db_path)
    if not snaps.empty:
        for m in snaps["month"].tolist():
            loaded = db.load_snapshot(str(m), db_path=db_path, shop_code=code)
            if not loaded:
                continue
            ro = loaded.get("raw_orders")
            if ro is not None and not ro.empty and ORDER_KEY in ro.columns:
                frames.append(ro)
            else:
                ln = loaded.get("lines")
                if ln is not None and not ln.empty and ORDER_KEY in ln.columns:
                    frames.append(ln)

    # 2. ดึงเสริมจากไฟล์ Excel ต้นฉบับใน data/uploads/ ของช่องนี้ (เผื่อมีไฟล์ Order เดือนก่อนหน้าที่อัปโหลดไว้)
    if include_uploads:
        ups = db.list_uploaded_excels(db_path=db_path, shop_code=code)
        if not ups.empty:
            udir = (db_path or db.DB_PATH).parent / "uploads"
            seen_files: set[tuple[str, int]] = set()
            # เรียงจากเก่าไปใหม่เพื่อให้ไฟล์อัปโหลดล่าสุดทับสถานะออเดอร์เก่าได้อย่างถูกต้อง
            for row in ups.iloc[::-1].itertuples(index=False):
                orig_name = str(getattr(row, "original_name", ""))
                if orig_name.lower().startswith("income"):
                    continue
                sig = (orig_name, int(getattr(row, "size_bytes", 0) or 0))
                if sig in seen_files:
                    continue
                seen_files.add(sig)
                fpath = udir / str(getattr(row, "stored_name", ""))
                if not fpath.exists():
                    continue
                try:
                    wb = load_workbook(BytesIO(fpath.read_bytes()), name=orig_name)
                    if wb.raw_orders is not None and not wb.raw_orders.empty:
                        frames.append(wb.raw_orders)
                except Exception:
                    continue

    if not frames:
        existing = _load_repo_direct(db_path, shop_code=code)
        tot = int(existing[ORDER_KEY].nunique()) if not existing.empty and ORDER_KEY in existing.columns else 0
        return {"added": 0, "replaced": 0, "total": tot}

    combined_raw = pd.concat(frames, ignore_index=True)
    res = _save_to_repo_direct(combined_raw, db_path=db_path, shop_code=code)
    _REPO_SUMMARY_CACHE.clear()
    return res


def ensure_repo_migrated(db_path: Path | None = None) -> None:
    """แยกไฟล์คลังคำสั่งซื้อเดิม (orders_raw.parquet) ออกตามร้านค้า และกู้คืนคลังของช่องย่อยที่เคยหายไปอัตโนมัติ (ทำครั้งเดียว)"""
    target_db = (db_path or db.DB_PATH).resolve()
    db_key = str(target_db)
    if db_key in _MIGRATED_DBS or _MIGRATING_NOW.get(db_key):
        return

    legacy_path = target_db.parent / "order_repo" / "orders_raw.parquet"
    if not target_db.exists() and not legacy_path.exists():
        return

    _MIGRATING_NOW[db_key] = True
    try:
        db.init_db(target_db)
        already_done = db.get_app_state(_MIGRATION_STATE_KEY, db_path=target_db) == "1"
        if already_done and not legacy_path.exists():
            _MIGRATED_DBS.add(db_key)
            return

        shops = db.list_shops(active_only=False, db_path=target_db)

        # ขั้นตอนที่ 1: หากยังมีไฟล์ orders_raw.parquet แบบรวมรุ่นเก่า ให้คัดแยกออเดอร์เข้าคลังของแต่ละร้านตามจริงแล้วลบไฟล์รวมทิ้ง
        if legacy_path.exists():
            try:
                legacy_df = _normalize_raw(pd.read_parquet(legacy_path))
            except Exception:
                legacy_df = pd.DataFrame()

            if not legacy_df.empty:
                oid_to_shop: dict[str, str] = {}
                for s in shops:
                    sc = normalize_shop_code(s["code"])
                    snaps = db.list_snapshots(shop_code=sc, db_path=target_db)
                    for m in snaps["month"].tolist() if not snaps.empty else []:
                        ld = db.load_snapshot(str(m), db_path=target_db, shop_code=sc)
                        if not ld:
                            continue
                        o_df = ld.get("orders")
                        if o_df is not None and not o_df.empty and "order_id" in o_df.columns:
                            for oid in o_df["order_id"].astype(str):
                                oid_to_shop[oid] = sc
                        ro_df = ld.get("raw_orders")
                        if ro_df is not None and not ro_df.empty and ORDER_KEY in ro_df.columns:
                            for oid in ro_df[ORDER_KEY].astype(str):
                                oid_to_shop[oid] = sc

                mapped_sc = legacy_df[ORDER_KEY].astype(str).map(oid_to_shop)
                matched_shops = {str(v) for v in mapped_sc.dropna().unique().tolist()}
                non_matang_matched = {v for v in matched_shops if v != "matang"}
                matang_has_snaps = not db.list_snapshots(shop_code="matang", db_path=target_db).empty

                if not matang_has_snaps and len(non_matang_matched) == 1:
                    fallback_sc = next(iter(non_matang_matched))
                else:
                    fallback_sc = "matang"

                final_sc = mapped_sc.fillna(fallback_sc)
                for sc_val, grp in legacy_df.groupby(final_sc):
                    _save_to_repo_direct(grp, db_path=target_db, shop_code=str(sc_val))

            legacy_path.unlink(missing_ok=True)

        # ขั้นตอนที่ 2: กู้คืนคลังคำสั่งซื้อของช่องย่อย (เช่น BUNGTEE, Dwine) ที่ยังไม่มีไฟล์แยกเฉพาะร้าน
        # แต่มีข้อมูล Snapshot หรือไฟล์อัปโหลดบันทึกอยู่ในระบบ
        if not already_done:
            for s in shops:
                sc = normalize_shop_code(s["code"])
                sname_low = str(s.get("name", "")).lower()
                p_sc = _repo_path(target_db, shop_code=sc)
                if p_sc.exists():
                    continue
                # เคารพกรณีที่ผู้ใช้ตั้งใจล้างคลังช่องมาตังไปแล้ว (ยกเว้นกรณีตั้งชื่อเป็น bungtee)
                if sc == "matang" and "bungtee" not in sname_low:
                    continue
                if can_rebuild_repo_for_shop(sc, db_path=target_db):
                    rebuild_repo_for_shop(sc, db_path=target_db, include_uploads=True)

        db.set_app_state(_MIGRATION_STATE_KEY, "1", db_path=target_db)
        _REPO_SUMMARY_CACHE.clear()
        _MIGRATED_DBS.add(db_key)
    finally:
        _MIGRATING_NOW.pop(db_key, None)


def load_repo(db_path: Path | None = None, shop_code: str | None = None) -> pd.DataFrame:
    ensure_repo_migrated(db_path)
    return _load_repo_direct(db_path, shop_code=shop_code)


def save_to_repo(raw_orders: pd.DataFrame, db_path: Path | None = None, shop_code: str | None = None) -> dict[str, int]:
    """บันทึกแถวคำสั่งซื้อลงคลังเฉพาะของร้านค้าที่ระบุ — ถ้า Order ID ซ้ำจะอัปเดตเป็นสถานะล่าสุด"""
    ensure_repo_migrated(db_path)
    return _save_to_repo_direct(raw_orders, db_path=db_path, shop_code=shop_code)


def _created_month(df: pd.DataFrame) -> pd.Series:
    if CREATED_COL not in df.columns:
        return pd.Series("ไม่ทราบเดือน", index=df.index)
    dt = pd.to_datetime(df[CREATED_COL], errors="coerce", format="mixed", dayfirst=True)
    return dt.dt.strftime("%Y-%m").fillna("ไม่ทราบเดือน")


def repo_summary(db_path: Path | None = None, shop_code: str | None = None) -> dict:
    """สรุปจำนวนออเดอร์ในคลังเฉพาะของร้านค้าที่ระบุ แยกตามเดือนที่สร้างคำสั่งซื้อ"""
    ensure_repo_migrated(db_path)
    p = _repo_path(db_path, shop_code=shop_code)
    cache_k = str(p)
    if not p.exists():
        _REPO_SUMMARY_CACHE.pop(cache_k, None)
        return {"orders": 0, "lines": 0, "months": pd.DataFrame(columns=["เดือนที่สั่งซื้อ", "จำนวนออเดอร์", "จำนวนแถวสินค้า"])}
    mtime = p.stat().st_mtime
    if cache_k in _REPO_SUMMARY_CACHE and _REPO_SUMMARY_CACHE[cache_k][0] == mtime:
        return _REPO_SUMMARY_CACHE[cache_k][1]

    repo = _load_repo_direct(db_path, shop_code=shop_code)
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
    """ล้างคลังคำสั่งซื้อสะสมเฉพาะของร้านค้าที่ระบุเท่านั้น (ไม่กระทบร้านอื่น 100%)"""
    ensure_repo_migrated(db_path)
    p = _repo_path(db_path, shop_code=shop_code)
    _REPO_SUMMARY_CACHE.pop(str(p), None)
    p.unlink(missing_ok=True)


def delete_month_from_repo(month: str, db_path: Path | None = None, shop_code: str | None = None) -> int:
    """ลบคำสั่งซื้อเฉพาะเดือนที่ระบุออกจากคลังของร้านค้าที่เลือกเท่านั้น คืนค่าจำนวนออเดอร์ที่ถูกลบ"""
    ensure_repo_migrated(db_path)
    repo = _load_repo_direct(db_path, shop_code=shop_code)
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
        _REPO_SUMMARY_CACHE.pop(str(p), None)
    return deleted_orders


def pull_for_settlement(
    settlement_ids: set[str],
    exclude_ids: set[str],
    db_path: Path | None = None,
    shop_code: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ดึงแถวคำสั่งซื้อจากคลังเฉพาะของร้านค้าที่ระบุ สำหรับ Order ID ที่อยู่ใน Income แต่ไม่มีในไฟล์รอบนี้"""
    repo = load_repo(db_path, shop_code=shop_code)
    if repo.empty or not settlement_ids:
        return pd.DataFrame(), pd.DataFrame()
    ids = repo[ORDER_KEY].astype(str)
    raw = repo[ids.isin(settlement_ids) & ~ids.isin(exclude_ids)].reset_index(drop=True)
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    return raw, orders_from_raw(raw, sheet_label="คลังคำสั่งซื้อสะสม")


def attach_repo_orders(data: LoadedWorkbook, db_path: Path | None = None, shop_code: str | None = None) -> tuple[LoadedWorkbook, int]:
    """เติมคำสั่งซื้อเดือนก่อนจากคลังเฉพาะของร้านค้าที่ระบุ เข้าไปในชุดข้อมูลที่จะคำนวณ"""
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
