"""หน้าหลัก — เรียบง่าย ตัวใหญ่ กดเข้าทำงานได้ทันที"""
from core.ui import init_page

init_page("หน้าหลัก", "🏠")

from core.reloader import ensure_fresh

ensure_fresh()

import streamlit as st

from core import db, order_repo
from core.pipeline import ALL_PERIODS_KEY
from core.ui import (
    baht,
    get_current_shop,
    load_period_result,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
    set_current_shop,
    summarize_for_period,
)

user = require_login()
cur_shop = get_current_shop()

skus = db.get_skus()
snapshots = db.list_snapshots(shop_code=cur_shop["code"])
valid_months = snapshots["month"].tolist() if not snapshots.empty else []
latest_period = valid_months[0] if valid_months else None
sess_period = st.session_state.get("period")
if sess_period and (sess_period in valid_months or (sess_period == ALL_PERIODS_KEY and len(valid_months) >= 2)):
    active_period = sess_period
else:
    active_period = latest_period or "-"

render_page_header(
    title="🏢 Matang Cosmetic Cost & Profit System",
    subtitle="ระบบอัตโนมัติคำนวณต้นทุนสินค้า (COGS), ค่าธรรมเนียม TikTok Shop และกำไรสุทธิแท้จริง แยกตามช่องทาง",
    period=active_period,
    shop=cur_shop,
)

# -----------------------------------------------------------------------------
# ศูนย์เลือกช่องทาง / ร้านค้า TikTok Shop (Channel Selection Gateway)
# -----------------------------------------------------------------------------
all_shops = db.list_shops(active_only=True)

render_section_header(
    "🏬 เลือกช่องทาง / ร้านค้า TikTok เพื่อเข้าทำงาน (Channel Gateway)",
    subtitle="กดเลือกช่องทางที่ต้องการจัดการ เพื่อแยกข้อมูล ออเดอร์ และไฟล์ต้นทุนอย่างปลอดภัย 100%",
    icon="🎯",
)

n_cols = max(1, min(len(all_shops), 4))
shop_cols = st.columns(n_cols, gap="medium")

for idx, s in enumerate(all_shops):
    col = shop_cols[idx % n_cols]
    s_code = s["code"]
    s_name = s["name"]
    s_handle = s.get("tiktok_handle") or ""
    is_active = (s_code == cur_shop["code"])

    s_snaps = db.list_snapshots(shop_code=s_code)
    s_periods_cnt = len(s_snaps)
    s_sales_total = float(s_snaps["net_sales"].sum()) if not s_snaps.empty and "net_sales" in s_snaps.columns else 0.0
    s_repo_cnt = order_repo.repo_summary(shop_code=s_code)["orders"]

    with col:
        border_color = "#4f46e5" if is_active else "#cbd5e1"
        bg_color = "linear-gradient(135deg, #eef2ff 0%, #ffffff 100%)" if is_active else "#ffffff"
        badge_html = (
            '<span style="background:#4f46e5;color:white;padding:3px 10px;border-radius:12px;font-size:0.75rem;font-weight:700;">🟢 กำลังทำงานในช่องนี้</span>'
            if is_active
            else '<span style="background:#f1f5f9;color:#64748b;padding:3px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;">⚪ ช่องทางย่อย</span>'
        )

        st.markdown(
            f"""
            <div style="background:{bg_color};border:2px solid {border_color};border-radius:16px;padding:16px 18px;margin-bottom:10px;box-shadow:0 4px 15px rgba(15,23,42,0.04);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <div style="font-size:1.5rem;">🏬</div>
                    <div>{badge_html}</div>
                </div>
                <div style="font-size:1.15rem;font-weight:800;color:#0f172a;line-height:1.3;min-height:48px;">
                    {s_name}
                </div>
                <div style="font-size:0.85rem;color:#6366f1;font-weight:600;margin-bottom:12px;">
                    {s_handle or '@ช่องทาง TikTok'}
                </div>
                <div style="background:#f8fafc;border-radius:10px;padding:10px 12px;font-size:0.85rem;color:#475569;display:flex;flex-direction:column;gap:4px;">
                    <div>📅 ข้อมูลที่บันทึก: <b>{s_periods_cnt:,} งวด</b></div>
                    <div>💰 ยอดขายสะสม: <b>{baht(s_sales_total) if user['role'] == 'admin' else '-'}</b></div>
                    <div>📦 คลังคำสั่งซื้อ: <b>{s_repo_cnt:,} ออเดอร์</b></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if is_active:
            st.button("✅ ใช้งานช่องนี้อยู่", key=f"active_btn_{s_code}", disabled=True, width="stretch")
        else:
            if st.button("👉 เลือกทำงานช่องนี้", key=f"switch_to_{s_code}", type="primary", width="stretch"):
                set_current_shop(s_code)
                st.rerun()

if user["role"] == "admin":
    with st.expander("➕ เพิ่ม/แก้ไข ช่องทาง TikTok Shop ใหม่"):
        col_add1, col_add2 = st.columns([1.5, 1.2])
        with col_add1:
            with st.form("form_home_add_shop", clear_on_submit=True):
                st.markdown("##### ➕ เพิ่มร้านค้า/ช่องทาง TikTok Shop ใหม่")
                add_code = st.text_input("รหัสช่องทาง (ภาษาอังกฤษ เช่น buntee2) *", placeholder="เช่น buntee2").strip().lower()
                add_name = st.text_input("ชื่อร้านค้า/ช่องทาง *", placeholder="เช่น ช่อง 2 BUNGTEE").strip()
                add_handle = st.text_input("TikTok Handle", placeholder="@bungtee_official").strip()
                add_def = st.checkbox("ตั้งเป็นร้านหลัก", value=False)
                if st.form_submit_button("บันทึกช่องทางใหม่", type="primary", width="stretch"):
                    if add_code and add_name:
                        db.upsert_shop(add_code, add_name, add_handle, is_default=add_def)
                        if add_def:
                            set_current_shop(db.get_default_shop()["code"])
                        st.toast(f"✅ เพิ่มช่องทาง {add_name} สำเร็จแล้ว", icon="🏬")
                        st.rerun()
                    else:
                        st.error("กรุณาระบุรหัสและชื่อร้าน")
        with col_add2:
            st.markdown("##### ℹ️ เกี่ยวกับระบบ Multi-Channel")
            st.caption(
                "• แต่ละช่องทางจะมีคลังคำสั่งซื้อสะสม (Order Repository) และข้อมูลงวดที่แยกจากกันอย่างสมบูรณ์ 100%\n"
                "• เมื่อคุณสลับช่องทาง ข้อมูล ยอดขาย และกำไรจะเปลี่ยนตามช่องทางนั้นทันที\n"
                "• สามารถส่งออกไฟล์ต้นทุนรวมเฉพาะของแต่ละช่องทางได้"
            )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# ข้อมูลสรุปของช่องทางที่เลือก (Selected Channel Overview)
# -----------------------------------------------------------------------------
total_periods = len(snapshots)
if not snapshots.empty and user["role"] == "admin":
    all_sales = float(snapshots["net_sales"].sum()) if "net_sales" in snapshots.columns else 0.0
    all_profit = float(snapshots["net_profit"].sum()) if "net_profit" in snapshots.columns else 0.0
else:
    all_sales = 0.0
    all_profit = 0.0

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    render_kpi_card(
        f"สินค้าในระบบทั้งหมด",
        f"{len(skus):,} รายการ",
        f"บันทึกแล้ว {total_periods:,} งวด ({cur_shop['name']})",
        delta="SKU Master Active",
        delta_positive=True,
        icon="📦",
    )
with c2:
    render_kpi_card(
        f"รายได้รวม ({cur_shop['name']})" if total_periods > 0 else f"รายได้รวม ({cur_shop['name']})",
        baht(all_sales) if (total_periods > 0 and user["role"] == "admin") else "-",
        f"งวดล่าสุด: {latest_period or 'ยังไม่มีข้อมูล'}",
        delta=f"{total_periods} งวดที่บันทึก" if total_periods > 0 else "ยังไม่มีงวด",
        icon="💰",
    )
with c3:
    render_kpi_card(
        f"กำไรสุทธิรวม ({cur_shop['name']})" if total_periods > 0 else f"กำไรสุทธิ ({cur_shop['name']})",
        baht(all_profit) if (total_periods > 0 and user["role"] == "admin") else "-",
        delta="กำไรสุทธิสะสม" if all_profit >= 0 else "ขาดทุนสะสม",
        delta_positive=all_profit >= 0,
        icon="📈",
    )

render_section_header("ขั้นตอนและเมนูการทำงานหลัก", subtitle="เลือกทำรายการที่ต้องการได้ทันที", icon="⚡")

m1, m2, m3 = st.columns(3, gap="medium")
with m1:
    with st.container(border=True):
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);color:white;display:flex;align-items:center;justify-content:center;font-size:1.35rem;box-shadow:0 4px 12px rgba(79,70,229,0.3);">
                    📤
                </div>
                <div>
                    <div style="font-size:1.15rem;font-weight:800;color:#0f172a;">1. นำเข้า & ส่งออกต้นทุน</div>
                    <div style="font-size:0.85rem;color:#64748b;font-weight:600;">เมนูหลัก (Core Action)</div>
                </div>
            </div>
            <p style="color:#475569;font-size:0.95rem;line-height:1.5;min-height:46px;">
                อัปโหลดไฟล์คำสั่งซื้อ + Income เพื่อคำนวณและสร้างไฟล์ต้นทุนรวม 7 ชีตฉบับสมบูรณ์ทันที
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_📤_นำเข้าข้อมูล.py", label="เปิดระบบนำเข้า & สร้างไฟล์ต้นทุน →", icon="📤", width="stretch")

if user["role"] == "admin":
    with m2:
        with st.container(border=True):
            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                    <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);color:white;display:flex;align-items:center;justify-content:center;font-size:1.35rem;box-shadow:0 4px 12px rgba(14,165,233,0.3);">
                        📦
                    </div>
                    <div>
                        <div style="font-size:1.15rem;font-weight:800;color:#0f172a;">2. จัดการสินค้า & ราคาทุน</div>
                        <div style="font-size:0.85rem;color:#64748b;font-weight:600;">SKU & Expenses</div>
                    </div>
                </div>
                <p style="color:#475569;font-size:0.95rem;line-height:1.5;min-height:46px;">
                    เพิ่ม/ลบ/แก้ไขราคาทุนสินค้า SKU และจัดการค่าคอมมิชชั่นกับค่าใช้จ่ายโรงงานรายเดือน
                </p>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/3_📦_สินค้าและต้นทุน.py", label="ไปหน้าจัดการสินค้า & ต้นทุน →", icon="📦", width="stretch")

    with m3:
        with st.container(border=True):
            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                    <div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg, #10b981 0%, #059669 100%);color:white;display:flex;align-items:center;justify-content:center;font-size:1.35rem;box-shadow:0 4px 12px rgba(16,185,129,0.3);">
                        📊
                    </div>
                    <div>
                        <div style="font-size:1.15rem;font-weight:800;color:#0f172a;">3. แดชบอร์ด & รายงาน</div>
                        <div style="font-size:0.85rem;color:#64748b;font-weight:600;">Analytics & Insights</div>
                    </div>
                </div>
                <p style="color:#475569;font-size:0.95rem;line-height:1.5;min-height:46px;">
                    ดูภาพรวมกำไรขาดทุน กราฟเส้นทางเงิน แยกรายสินค้า และแนวโน้มรายเดือนแบบละเอียด
                </p>
                """,
                unsafe_allow_html=True,
            )
            st.page_link("pages/1_📊_แดชบอร์ด.py", label="เปิดแดชบอร์ดวิเคราะห์กำไร →", icon="📊", width="stretch")

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# กล่องคู่มือแนะนำการใช้งานด่วน (Cheat Sheet)
st.markdown(
    """
    <div style="background:#ffffff; border:1px solid rgba(226, 232, 240, 0.9); border-radius:18px; padding:24px 28px; margin-top:16px; box-shadow:0 4px 20px -2px rgba(15, 23, 42, 0.04);">
        <div style="font-size:1.25rem; font-weight:800; color:#0f172a; margin-bottom:16px; display:flex; align-items:center; gap:10px;">
            <div style="width:36px;height:36px;border-radius:10px;background:rgba(79,70,229,0.1);color:#4f46e5;display:flex;align-items:center;justify-content:center;font-size:1.2rem;">📖</div>
            คู่มือเริ่มต้นใช้งานด่วน: อะไรเป็นอะไร & ต้องทำอะไรบ้าง (3 ขั้นตอนง่ายๆ)
        </div>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:18px; margin-bottom:20px;">
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:18px;">
                <div style="font-size:0.82rem; font-weight:800; color:#4f46e5; text-transform:uppercase; letter-spacing:0.04em;">ขั้นตอนที่ 1</div>
                <div style="font-size:1.1rem; font-weight:800; color:#0f172a; margin:6px 0 8px 0;">เตรียม 2 ไฟล์จาก TikTok</div>
                <div style="font-size:0.92rem; color:#475569; line-height:1.55;">
                    • <b>ไฟล์คำสั่งซื้อ (Order):</b> โหลดจากหน้า <i>Orders</i> (ชื่อไฟล์ขึ้นต้นด้วย <code>ทั้งหมด คำสั่งซื้อ...</code>)<br>
                    • <b>ไฟล์รายได้ (Income):</b> โหลดจากหน้า <i>Finances</i> (ชื่อไฟล์ขึ้นต้นด้วย <code>income_...</code>)
                </div>
            </div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:18px;">
                <div style="font-size:0.82rem; font-weight:800; color:#0ea5e9; text-transform:uppercase; letter-spacing:0.04em;">ขั้นตอนที่ 2</div>
                <div style="font-size:1.1rem; font-weight:800; color:#0f172a; margin:6px 0 8px 0;">วางไฟล์ลง 2 ช่อง & กดคำนวณ</div>
                <div style="font-size:0.92rem; color:#475569; line-height:1.55;">
                    เปิดหน้า <b>"📤 นำเข้าข้อมูล"</b> วางไฟล์ลง 2 ช่องให้ตรงชื่อ แล้วกดปุ่ม <b>"⚙️ คำนวณ"</b> ระบบจะดึงราคาทุน SKU มาคำนวณและสรุปกำไรให้ทันที
                </div>
            </div>
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:18px;">
                <div style="font-size:0.82rem; font-weight:800; color:#10b981; text-transform:uppercase; letter-spacing:0.04em;">ขั้นตอนที่ 3</div>
                <div style="font-size:1.1rem; font-weight:800; color:#0f172a; margin:6px 0 8px 0;">ดาวน์โหลดไฟล์ต้นทุนรวม</div>
                <div style="font-size:0.92rem; color:#475569; line-height:1.55;">
                    กดปุ่ม <b>"⬇️ ดาวน์โหลดไฟล์ต้นทุนรวม"</b> จะได้ไฟล์ Excel สมบูรณ์ 7 ชีตตรงมาตรฐานเดิม ส่งต่อฝ่ายบัญชีหรือผู้บริหารได้ทันที
                </div>
            </div>
        </div>
        <div style="background:linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius:12px; padding:14px 20px; font-size:0.92rem; color:#334155; line-height:1.6;">
            <b>📌 ความหมายของตัวเลขสำคัญ (สรุปให้เข้าใจง่าย):</b><br>
            • <b>Col F (ยอดการชำระเงิน):</b> เงินสุทธิที่ TikTok โอนเข้าบัญชีบริษัทจริง (หักค่าคอมฯ และค่าธรรมเนียมแล้ว)<br>
            • <b>Col G (ต้นทุนรวม COGS):</b> ราคาทุนสินค้าจริงของสินค้าที่จัดส่งสำเร็จ (ราคาทุน SKU × จำนวนชิ้น)<br>
            • <b>Col H (กำไรสุทธิแท้จริง):</b> เงินเหลือเข้ากระเป๋าบริษัทจริง คำนวณจากสูตร <code>เงินที่ TikTok โอน (F) − ต้นทุนสินค้า (G)</code>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
