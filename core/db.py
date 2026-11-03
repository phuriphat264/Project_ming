"""ฐานข้อมูล SQLite ภายในเครื่อง: ผู้ใช้, ราคาทุนสินค้า (SKU) และต้นทุนคงที่"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import bcrypt
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SKU_COLUMNS = ["sku", "name", "category", "unit_cost", "retail_price", "promo_price", "list_price"]
SKU_LABELS = {
    "sku": "รหัส",
    "name": "ชื่อ",
    "category": "หมวดหมู่",
    "unit_cost": "ราคาทุน",
    "retail_price": "ราคาปลีก",
    "promo_price": "ราคาโปร",
    "list_price": "ราคาตั้งขาย",
}


@contextmanager
def connect(db_path: Path | None = None):
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'staff')),
                display_name TEXT
            );
            CREATE TABLE IF NOT EXISTS sku (
                sku TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                unit_cost REAL NOT NULL DEFAULT 0,
                retail_price REAL DEFAULT 0,
                promo_price REAL DEFAULT 0,
                list_price REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS fixed_costs (
                month TEXT NOT NULL,          -- รูปแบบ YYYY-MM
                item TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (month, item)
            );
            CREATE TABLE IF NOT EXISTS monthly_settings (
                month TEXT PRIMARY KEY,
                labor REAL NOT NULL DEFAULT 0,
                water REAL NOT NULL DEFAULT 0,
                electric REAL NOT NULL DEFAULT 0,
                other REAL NOT NULL DEFAULT 0,
                comm_pct REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS monthly_snapshots (
                month TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                source TEXT,
                order_count INTEGER,
                net_sales REAL,
                net_profit REAL,
                warnings_json TEXT
            );
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploaded_at TEXT NOT NULL,
                period TEXT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                uploaded_by TEXT
            );
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS shops (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tiktok_handle TEXT DEFAULT '',
                is_default INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )
        # รองรับฐานข้อมูลเดิมที่ยังไม่มีคอลัมน์ list_price (ราคาตั้งขาย)
        existing_cols = {r[1] for r in c.execute("PRAGMA table_info(sku)").fetchall()}
        if "list_price" not in existing_cols:
            c.execute("ALTER TABLE sku ADD COLUMN list_price REAL DEFAULT 0")

        # เพิ่มคอลัมน์ shop_code ใน monthly_snapshots หากยังไม่มี
        snap_cols = {r[1] for r in c.execute("PRAGMA table_info(monthly_snapshots)").fetchall()}
        if "shop_code" not in snap_cols:
            c.execute("ALTER TABLE monthly_snapshots ADD COLUMN shop_code TEXT DEFAULT 'matang'")

        # เมล็ดพันธุ์ร้านค้าเริ่มต้น (มาตัง และ ดีไวน์)
        if c.execute("SELECT COUNT(*) FROM shops").fetchone()[0] == 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(
                "INSERT INTO shops (code, name, tiktok_handle, is_default, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("matang", "มาตัง (Matang)", "@matang_official", 1, 1, now_str),
            )
            c.execute(
                "INSERT INTO shops (code, name, tiktok_handle, is_default, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("dwine", "ดีไวน์ (Dwine)", "@dwine_thailand", 0, 1, now_str),
            )

        # บัญชีเริ่มต้น (ควรเปลี่ยนรหัสผ่านหลังติดตั้ง)
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            for user, pw, role, display in (
                ("admin", "admin123", "admin", "ผู้บริหาร"),
                ("staff", "staff123", "staff", "พนักงาน"),
            ):
                c.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?)",
                    (user, _hash(pw), role, display),
                )

        # เมล็ดพันธุ์ SKU เริ่มต้น หากตารางยังว่างเปล่า (รองรับการ clone โปรเจกต์ใหม่)
        if c.execute("SELECT COUNT(*) FROM sku").fetchone()[0] == 0:
            default_sku_csv = Path(__file__).resolve().parent.parent / "data" / "default_master_skus.csv"
            if default_sku_csv.exists():
                try:
                    seed_df = pd.read_csv(default_sku_csv, encoding="utf-8-sig")
                    seed_df = _normalize_sku_frame(seed_df)
                    placeholders = ", ".join(["?"] * len(SKU_COLUMNS))
                    c.executemany(
                        f"INSERT INTO sku ({', '.join(SKU_COLUMNS)}) VALUES ({placeholders})",
                        seed_df[SKU_COLUMNS].itertuples(index=False, name=None),
                    )
                except Exception:
                    pass


# ---------- shops (multi-channel support) ----------
def list_shops(active_only: bool = False, db_path: Path | None = None) -> list[dict]:
    """ดึงรายชื่อช่องทาง / ร้านค้า TikTok ทั้งหมดในระบบ"""
    init_db(db_path)
    with connect(db_path) as c:
        where = "WHERE is_active = 1" if active_only else ""
        rows = c.execute(
            f"""
            SELECT code, name, tiktok_handle, is_default, is_active, created_at
            FROM shops
            {where}
            ORDER BY is_default DESC, name ASC
            """
        ).fetchall()
        return [
            {
                "code": r[0],
                "name": r[1],
                "tiktok_handle": r[2] or "",
                "is_default": bool(r[3]),
                "is_active": bool(r[4]),
                "created_at": r[5],
            }
            for r in rows
        ]


def get_default_shop(db_path: Path | None = None) -> dict:
    shops = list_shops(active_only=True, db_path=db_path)
    for s in shops:
        if s["is_default"]:
            return s
    return shops[0] if shops else {"code": "matang", "name": "มาตัง (Matang)", "tiktok_handle": "@matang_official", "is_default": True, "is_active": True}


def get_shop(code: str, db_path: Path | None = None) -> dict | None:
    """ดึงข้อมูลร้านค้า 1 ร้านตามรหัส code"""
    code = code.strip().lower()
    for s in list_shops(active_only=False, db_path=db_path):
        if s["code"] == code:
            return s
    return None


def upsert_shop(
    code: str,
    name: str,
    tiktok_handle: str = "",
    is_default: bool = False,
    is_active: bool = True,
    db_path: Path | None = None,
) -> None:
    code = code.strip().lower()
    name = name.strip()
    if not code or not name:
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with connect(db_path) as c:
        if is_default:
            c.execute("UPDATE shops SET is_default = 0")
        c.execute(
            """
            INSERT INTO shops (code, name, tiktok_handle, is_default, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                tiktok_handle = excluded.tiktok_handle,
                is_default = excluded.is_default,
                is_active = excluded.is_active
            """,
            (code, name, tiktok_handle.strip(), 1 if is_default else 0, 1 if is_active else 0, now_str),
        )


def delete_shop(code: str, db_path: Path | None = None) -> bool:
    code = code.strip().lower()
    if code in ("matang",):
        return False  # Protect default main shop
    with connect(db_path) as c:
        c.execute("DELETE FROM shops WHERE code = ?", (code,))
    return True


def detect_shop_from_text(text: str, db_path: Path | None = None) -> dict | None:
    """ตรวจจับว่าข้อความหรือชื่อไฟล์ตรงกับชื่อร้านหรือรหัสร้านไหน โดยให้ความสำคัญกับคำที่ยาว/เจาะจงก่อน"""
    if not text:
        return None
    shops = list_shops(active_only=True, db_path=db_path)
    clean_text = str(text).lower()

    candidates = []
    for s in shops:
        keys = [s["code"]]
        if s["tiktok_handle"]:
            keys.append(s["tiktok_handle"].lower().lstrip("@"))
        for p in s["name"].lower().split():
            part = p.strip("()[]- _")
            if len(part) >= 3:
                keys.append(part)
        for k in keys:
            if k in clean_text:
                candidates.append((len(k), not s["is_default"], s))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]
    return None


# ---------- users ----------
def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_user(username: str, password: str, db_path: Path | None = None) -> dict | None:
    with connect(db_path) as c:
        row = c.execute(
            "SELECT username, password_hash, role, display_name FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if row and bcrypt.checkpw(password.encode(), row[1].encode()):
        return {"username": row[0], "role": row[2], "display_name": row[3] or row[0]}
    return None


def list_users(db_path: Path | None = None) -> pd.DataFrame:
    with connect(db_path) as c:
        return pd.read_sql("SELECT username, role, display_name FROM users ORDER BY username", c)


def upsert_user(username: str, password: str, role: str, display_name: str = "", db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, "
            "role=excluded.role, display_name=excluded.display_name",
            (username.strip(), _hash(password), role, display_name),
        )


def delete_user(username: str, db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.execute("DELETE FROM users WHERE username = ?", (username,))


def set_app_state(key: str, value: str, db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_app_state(key: str, db_path: Path | None = None) -> str | None:
    with connect(db_path) as c:
        row = c.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row and row[0] else None


def save_remembered_user(username: str, db_path: Path | None = None) -> None:
    set_app_state("remembered_user", username.strip(), db_path)


def clear_remembered_user(db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.execute("DELETE FROM app_state WHERE key = 'remembered_user'")


def get_remembered_user(db_path: Path | None = None) -> dict | None:
    uname = get_app_state("remembered_user", db_path)
    if not uname:
        return None
    with connect(db_path) as c:
        row = c.execute(
            "SELECT username, role, display_name FROM users WHERE username = ?",
            (uname,),
        ).fetchone()
    if row:
        return {"username": row[0], "role": row[1], "display_name": row[2] or row[0]}
    return None


# ---------- SKU master ----------
def get_skus(db_path: Path | None = None) -> pd.DataFrame:
    with connect(db_path) as c:
        return pd.read_sql(f"SELECT {', '.join(SKU_COLUMNS)} FROM sku ORDER BY sku", c)


def save_skus(df: pd.DataFrame, db_path: Path | None = None) -> None:
    """แทนที่ตาราง SKU ทั้งหมดด้วย df (ใช้กับตารางแก้ไขบนหน้าเว็บ)"""
    df = _normalize_sku_frame(df)
    placeholders = ", ".join(["?"] * len(SKU_COLUMNS))
    with connect(db_path) as c:
        c.execute("DELETE FROM sku")
        c.executemany(
            f"INSERT INTO sku ({', '.join(SKU_COLUMNS)}) VALUES ({placeholders})",
            df[SKU_COLUMNS].itertuples(index=False, name=None),
        )


def upsert_sku(
    sku: str,
    name: str = "",
    category: str = "",
    unit_cost: float = 0.0,
    retail_price: float = 0.0,
    promo_price: float = 0.0,
    list_price: float = 0.0,
    db_path: Path | None = None,
) -> None:
    """เพิ่มหรืออัปเดต SKU เดี่ยว 1 รายการ"""
    df = pd.DataFrame([{
        "sku": str(sku).strip(),
        "name": str(name).strip(),
        "category": str(category).strip(),
        "unit_cost": float(unit_cost),
        "retail_price": float(retail_price),
        "promo_price": float(promo_price),
        "list_price": float(list_price),
    }])
    upsert_skus(df, db_path=db_path)


def upsert_skus(df: pd.DataFrame, db_path: Path | None = None) -> int:
    """เพิ่ม/อัปเดต SKU จาก df โดยไม่ลบตัวที่มีอยู่"""
    df = _normalize_sku_frame(df)
    placeholders = ", ".join(["?"] * len(SKU_COLUMNS))
    with connect(db_path) as c:
        c.executemany(
            f"INSERT INTO sku ({', '.join(SKU_COLUMNS)}) VALUES ({placeholders}) "
            "ON CONFLICT(sku) DO UPDATE SET "
            "name=CASE WHEN excluded.name IS NOT NULL AND excluded.name != '' THEN excluded.name ELSE sku.name END, "
            "category=CASE WHEN excluded.category IS NOT NULL AND excluded.category != '' THEN excluded.category ELSE sku.category END, "
            "unit_cost=CASE WHEN excluded.unit_cost > 0 THEN excluded.unit_cost ELSE sku.unit_cost END, "
            "retail_price=CASE WHEN excluded.retail_price > 0 THEN excluded.retail_price ELSE sku.retail_price END, "
            "promo_price=CASE WHEN excluded.promo_price > 0 THEN excluded.promo_price ELSE sku.promo_price END, "
            "list_price=CASE WHEN excluded.list_price > 0 THEN excluded.list_price ELSE sku.list_price END",
            df[SKU_COLUMNS].itertuples(index=False, name=None),
        )
    return len(df)


def add_missing_skus(skus: pd.DataFrame, db_path: Path | None = None) -> int:
    """เพิ่ม SKU ที่ยังไม่มีในระบบ และเติมราคาทุนอัตโนมัติถ้าเดิมเป็น 0 แล้วพบราคาทุนในชีต Order (ไม่ทับราคาทุนที่มีอยู่แล้ว)"""
    df = _normalize_sku_frame(skus)
    if df.empty:
        return 0
    placeholders = ", ".join(["?"] * len(SKU_COLUMNS))
    with connect(db_path) as c:
        before = c.execute("SELECT COUNT(*) FROM sku").fetchone()[0]
        c.executemany(
            f"INSERT INTO sku ({', '.join(SKU_COLUMNS)}) VALUES ({placeholders}) "
            "ON CONFLICT(sku) DO UPDATE SET "
            "name = CASE WHEN (sku.name IS NULL OR sku.name = '') AND excluded.name != '' THEN excluded.name ELSE sku.name END, "
            "category = CASE WHEN (sku.category IS NULL OR sku.category = '') AND excluded.category != '' THEN excluded.category ELSE sku.category END, "
            "unit_cost = CASE WHEN sku.unit_cost <= 0 AND excluded.unit_cost > 0 THEN excluded.unit_cost ELSE sku.unit_cost END, "
            "list_price = CASE WHEN sku.list_price <= 0 AND excluded.list_price > 0 THEN excluded.list_price ELSE sku.list_price END",
            df[SKU_COLUMNS].itertuples(index=False, name=None),
        )
        after = c.execute("SELECT COUNT(*) FROM sku").fetchone()[0]
    return after - before


def delete_sku(sku: str, db_path: Path | None = None) -> None:
    """ลบรหัสสินค้า 1 รายการออกจากตาราง sku"""
    with connect(db_path) as c:
        c.execute("DELETE FROM sku WHERE sku = ?", (sku.strip(),))


def clear_all_skus(db_path: Path | None = None) -> None:
    """ลบข้อมูลสินค้าและต้นทุนทั้งหมดในตาราง sku"""
    with connect(db_path) as c:
        c.execute("DELETE FROM sku")


def _normalize_sku_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    num_cols = ("unit_cost", "retail_price", "promo_price", "list_price")
    for col in SKU_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col in num_cols else ""
    df["sku"] = df["sku"].astype(str).str.strip()
    df = df[(df["sku"] != "") & (df["sku"].str.lower() != "nan")]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in ("name", "category"):
        df[col] = df[col].fillna("").astype(str)
    return df.drop_duplicates(subset="sku", keep="first")


# ---------- fixed costs ----------
def get_fixed_costs(month: str, db_path: Path | None = None) -> pd.DataFrame:
    with connect(db_path) as c:
        return pd.read_sql(
            "SELECT item, amount FROM fixed_costs WHERE month = ? ORDER BY item", c, params=(month,)
        )


def save_fixed_costs(month: str, df: pd.DataFrame, db_path: Path | None = None) -> None:
    df = df.copy()
    df["item"] = df["item"].fillna("").astype(str).str.strip()
    df = df[df["item"] != ""]
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    with connect(db_path) as c:
        c.execute("DELETE FROM fixed_costs WHERE month = ?", (month,))
        c.executemany(
            "INSERT INTO fixed_costs (month, item, amount) VALUES (?, ?, ?)",
            [(month, r.item, r.amount) for r in df.itertuples(index=False)],
        )


def total_fixed_cost(month: str, db_path: Path | None = None) -> float:
    if not month:
        return 0.0
    with connect(db_path) as c:
        v = c.execute("SELECT COALESCE(SUM(amount), 0) FROM fixed_costs WHERE month = ?", (month,)).fetchone()[0]
    return float(v)


def upsert_fixed_cost_item(
    month: str,
    item: str,
    amount: float,
    old_item: str | None = None,
    db_path: Path | None = None,
) -> None:
    """เพิ่มหรือแก้ไขรายการค่าใช้จ่ายคงที่รายตัวในงวดที่ระบุ"""
    clean_item = item.strip()
    if not clean_item:
        return
    with connect(db_path) as c:
        if old_item and old_item.strip() != clean_item:
            c.execute("DELETE FROM fixed_costs WHERE month = ? AND item = ?", (month, old_item.strip()))
        c.execute(
            """
            INSERT INTO fixed_costs (month, item, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(month, item) DO UPDATE SET amount = excluded.amount
            """,
            (month, clean_item, float(amount)),
        )


def delete_fixed_cost_item(month: str, item: str, db_path: Path | None = None) -> None:
    """ลบรายการค่าใช้จ่ายคงที่ 1 รายการ"""
    with connect(db_path) as c:
        c.execute("DELETE FROM fixed_costs WHERE month = ? AND item = ?", (month, item.strip()))


def clear_fixed_costs(month: str, db_path: Path | None = None) -> None:
    """ลบรายการค่าใช้จ่ายคงที่ทั้งหมดในงวดที่ระบุ"""
    with connect(db_path) as c:
        c.execute("DELETE FROM fixed_costs WHERE month = ?", (month,))


def get_comm_pct(month: str, db_path: Path | None = None) -> float:
    """ดึง % ค่าคอมมิชชั่นคนขายประจำงวด"""
    if not month:
        return 0.0
    with connect(db_path) as c:
        row = c.execute("SELECT comm_pct FROM monthly_settings WHERE month = ?", (month,)).fetchone()
    return float(row[0]) if row else 0.0


def save_comm_pct(month: str, comm_pct: float, db_path: Path | None = None) -> None:
    """บันทึก % ค่าคอมมิชชั่นคนขายประจำงวด"""
    if not month:
        return
    with connect(db_path) as c:
        c.execute(
            """
            INSERT INTO monthly_settings (month, labor, water, electric, other, comm_pct)
            VALUES (?, 0, 0, 0, 0, ?)
            ON CONFLICT(month) DO UPDATE SET comm_pct = excluded.comm_pct
            """,
            (month, float(comm_pct)),
        )


def list_expense_months(db_path: Path | None = None) -> list[str]:
    """ดึงรายชื่องวดเดือนทั้งหมดที่มีการตั้งค่าค่าใช้จ่ายหรือสแนปช็อต"""
    with connect(db_path) as c:
        m1 = [r[0] for r in c.execute("SELECT DISTINCT month FROM fixed_costs").fetchall()]
        m2 = [r[0] for r in c.execute("SELECT DISTINCT month FROM monthly_snapshots").fetchall()]
        m3 = [r[0] for r in c.execute("SELECT DISTINCT month FROM monthly_settings").fetchall()]
    return sorted({m for m in (m1 + m2 + m3) if m}, reverse=True)


# ---------- monthly snapshots (persistent history) ----------
def _snapshot_dir(db_path: Path | None = None) -> Path:
    p = (db_path or DB_PATH).parent / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_month_stem(month: str) -> str:
    """ป้องกันอักขระพิเศษในชื่องวดไม่ให้กระทบชื่อไฟล์ Parquet"""
    s = str(month).strip()
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
        s = s.replace(ch, "-")
    return s or "unknown"


def save_snapshot(
    month: str,
    summary_dict: dict,
    orders_df: pd.DataFrame,
    lines_df: pd.DataFrame,
    ads_df: pd.DataFrame,
    source: str,
    warnings: list[str],
    fee_details: dict[str, float] | None = None,
    withdrawals_df: pd.DataFrame | None = None,
    raw_settlement_df: pd.DataFrame | None = None,
    raw_orders_df: pd.DataFrame | None = None,
    shop_code: str | None = None,
    db_path: Path | None = None,
) -> None:
    sdir = _snapshot_dir(db_path)
    stem = _safe_month_stem(month)
    # เก็บไฟล์ DataFrame ในรูปแบบ Parquet (บีบอัด เร็ว ประหยัดพื้นที่)
    orders_path = sdir / f"{stem}_orders.parquet"
    lines_path = sdir / f"{stem}_lines.parquet"
    ads_path = sdir / f"{stem}_ads.parquet"
    wd_path = sdir / f"{stem}_withdrawals.parquet"
    raw_s_path = sdir / f"{stem}_raw_settle.parquet"
    raw_o_path = sdir / f"{stem}_raw_orders.parquet"

    orders_df.to_parquet(orders_path, index=False)
    lines_df.to_parquet(lines_path, index=False) if not lines_df.empty else lines_path.unlink(missing_ok=True)
    ads_df.to_parquet(ads_path, index=False) if not ads_df.empty else ads_path.unlink(missing_ok=True)
    if withdrawals_df is not None and not withdrawals_df.empty:
        withdrawals_df.to_parquet(wd_path, index=False)
    else:
        wd_path.unlink(missing_ok=True)
    if raw_settlement_df is not None and not raw_settlement_df.empty:
        raw_settlement_df.to_parquet(raw_s_path, index=False)
    if raw_orders_df is not None and not raw_orders_df.empty:
        raw_orders_df.to_parquet(raw_o_path, index=False)

    payload = dict(summary_dict)
    if fee_details:
        payload["_fee_details"] = fee_details

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    net_sales = float(summary_dict.get("net_sales", 0.0))
    net_profit = float(summary_dict.get("net_profit", 0.0))
    order_count = int(summary_dict.get("orders", len(orders_df)))

    # กำหนด shop_code หากไม่ได้ระบุ
    if not shop_code:
        if "ดีไวน์" in month or "dwine" in month.lower():
            shop_code = "dwine"
        elif "รวม" in month:
            shop_code = "all"
        else:
            m_shop = re.search(r"\(([^)]+)\)", month)
            if m_shop:
                shop_code = m_shop.group(1).strip().lower()
            else:
                shop_code = "matang"

    with connect(db_path) as c:
        c.execute(
            """
            INSERT INTO monthly_snapshots
            (month, created_at, summary_json, source, order_count, net_sales, net_profit, warnings_json, shop_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                created_at = excluded.created_at,
                summary_json = excluded.summary_json,
                source = excluded.source,
                order_count = excluded.order_count,
                net_sales = excluded.net_sales,
                net_profit = excluded.net_profit,
                warnings_json = excluded.warnings_json,
                shop_code = excluded.shop_code
            """,
            (
                month,
                now,
                json.dumps(payload, ensure_ascii=False),
                source,
                order_count,
                net_sales,
                net_profit,
                json.dumps(warnings, ensure_ascii=False),
                shop_code,
            ),
        )


def list_snapshots(db_path: Path | None = None) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as c:
        return pd.read_sql(
            """
            SELECT month, created_at, source, order_count, net_sales, net_profit, shop_code
            FROM monthly_snapshots
            ORDER BY month DESC
            """,
            c,
        )


def load_snapshot(month: str, db_path: Path | None = None) -> dict | None:
    init_db(db_path)
    with connect(db_path) as c:
        row = c.execute(
            """
            SELECT summary_json, source, warnings_json, shop_code
            FROM monthly_snapshots WHERE month = ?
            """,
            (month,),
        ).fetchone()

    if not row:
        return None

    sdir = _snapshot_dir(db_path)
    stem = _safe_month_stem(month)
    orders_path = sdir / f"{stem}_orders.parquet"
    if not orders_path.exists() and stem != month:
        stem = month
        orders_path = sdir / f"{stem}_orders.parquet"
    lines_path = sdir / f"{stem}_lines.parquet"
    ads_path = sdir / f"{stem}_ads.parquet"
    wd_path = sdir / f"{stem}_withdrawals.parquet"
    raw_s_path = sdir / f"{stem}_raw_settle.parquet"
    raw_o_path = sdir / f"{stem}_raw_orders.parquet"

    if not orders_path.exists():
        return None

    orders_df = pd.read_parquet(orders_path)
    lines_df = pd.read_parquet(lines_path) if lines_path.exists() else pd.DataFrame()
    ads_df = pd.read_parquet(ads_path) if ads_path.exists() else pd.DataFrame()
    wd_df = pd.read_parquet(wd_path) if wd_path.exists() else pd.DataFrame()
    raw_s_df = pd.read_parquet(raw_s_path) if raw_s_path.exists() else pd.DataFrame()
    raw_o_df = pd.read_parquet(raw_o_path) if raw_o_path.exists() else pd.DataFrame()

    parsed_summary = json.loads(row[0])
    fee_details = parsed_summary.pop("_fee_details", {}) if isinstance(parsed_summary, dict) else {}

    return {
        "month": month,
        "summary": parsed_summary,
        "fee_details": fee_details,
        "source": row[1],
        "warnings": json.loads(row[2]) if row[2] else [],
        "shop_code": row[3] if len(row) > 3 and row[3] else "matang",
        "orders": orders_df,
        "lines": lines_df,
        "ads": ads_df,
        "withdrawals": wd_df,
        "raw_settlement": raw_s_df,
        "raw_orders": raw_o_df,
    }


def delete_snapshot(month: str, db_path: Path | None = None) -> None:
    sdir = _snapshot_dir(db_path)
    for stem in {month, _safe_month_stem(month)}:
        for ext in ("_orders.parquet", "_lines.parquet", "_ads.parquet", "_withdrawals.parquet", "_raw_settle.parquet", "_raw_orders.parquet"):
            p = sdir / f"{stem}{ext}"
            if p.exists():
                p.unlink(missing_ok=True)
    with connect(db_path) as c:
        c.execute("DELETE FROM monthly_snapshots WHERE month = ?", (month,))


# ---------- uploaded Excel backups (data/uploads/) ----------
def _uploads_dir(db_path: Path | None = None) -> Path:
    p = (db_path or DB_PATH).parent / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_uploaded_excel(
    original_name: str,
    raw_bytes: bytes,
    period: str = "",
    uploaded_by: str = "",
    db_path: Path | None = None,
) -> Path:
    """บันทึกสำเนาไฟล์ Excel ต้นฉบับไว้ในโฟลเดอร์ data/uploads/ พร้อมเก็บประวัติลง SQLite"""
    udir = _uploads_dir(db_path)
    now = datetime.now()
    safe_name = Path(original_name).name.replace("/", "_").replace("\\", "_")
    prefix = f"{_safe_month_stem(period)}_" if period and period != "ไม่ทราบงวด" else ""
    stored_name = f"{prefix}{now:%Y%m%d_%H%M%S}_{safe_name}"
    target_path = udir / stored_name
    target_path.write_bytes(raw_bytes)

    with connect(db_path) as c:
        c.execute(
            """
            INSERT INTO uploaded_files (uploaded_at, period, original_name, stored_name, size_bytes, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (now.strftime("%Y-%m-%d %H:%M:%S"), period, safe_name, stored_name, len(raw_bytes), uploaded_by),
        )
    return target_path


def list_uploaded_excels(db_path: Path | None = None) -> pd.DataFrame:
    udir = _uploads_dir(db_path)
    with connect(db_path) as c:
        df = pd.read_sql(
            """
            SELECT id, uploaded_at, period, original_name, stored_name, size_bytes, uploaded_by
            FROM uploaded_files
            ORDER BY id DESC
            """,
            c,
        )
    if df.empty:
        return df
    # แสดงเฉพาะไฟล์ที่ยังมีอยู่จริงใน data/uploads/
    exists_mask = df["stored_name"].apply(lambda n: (udir / str(n)).exists())
    return df[exists_mask].reset_index(drop=True)


def get_uploaded_excel_path(file_id: int, db_path: Path | None = None) -> tuple[str, Path] | None:
    udir = _uploads_dir(db_path)
    with connect(db_path) as c:
        row = c.execute("SELECT original_name, stored_name FROM uploaded_files WHERE id = ?", (int(file_id),)).fetchone()
    if not row:
        return None
    p = udir / row[1]
    return (row[0], p) if p.exists() else None


def delete_uploaded_excel(file_id: int, db_path: Path | None = None) -> None:
    udir = _uploads_dir(db_path)
    with connect(db_path) as c:
        row = c.execute("SELECT stored_name FROM uploaded_files WHERE id = ?", (int(file_id),)).fetchone()
        if row:
            (udir / row[0]).unlink(missing_ok=True)
        c.execute("DELETE FROM uploaded_files WHERE id = ?", (int(file_id),))


# ---------- One-Click Full Backup & Restore (.zip) ----------
def create_backup_zip_bytes(db_path: Path | None = None) -> bytes:
    """สำรองฐานข้อมูล app.db, snapshots/ และ uploads/ รวมเป็นไฟล์ zip ก้อนเดียว"""
    import io
    import zipfile

    p = db_path or DB_PATH
    data_dir = p.parent
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if p.exists():
            zf.write(p, arcname="app.db")
        snap_dir = data_dir / "snapshots"
        if snap_dir.exists():
            for f in snap_dir.glob("*.parquet"):
                zf.write(f, arcname=f"snapshots/{f.name}")
        up_dir = data_dir / "uploads"
        if up_dir.exists():
            for f in up_dir.iterdir():
                if f.is_file():
                    zf.write(f, arcname=f"uploads/{f.name}")
        repo_dir = data_dir / "order_repo"
        if repo_dir.exists():
            for f in repo_dir.glob("*.parquet"):
                zf.write(f, arcname=f"order_repo/{f.name}")
    return buf.getvalue()


def restore_backup_from_zip(zip_bytes: bytes, db_path: Path | None = None) -> int:
    """กู้คืนข้อมูลทั้งหมดจากไฟล์ backup zip"""
    import io
    import zipfile

    p = db_path or DB_PATH
    data_dir = p.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            # ป้องกัน path traversal
            safe_rel = Path(name).name if "/" not in name else Path(name)
            target = data_dir / safe_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
            count += 1
    return count


