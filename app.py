"""หน้าหลัก — เรียบง่าย ตัวใหญ่ กดเข้าทำงานได้ทันที"""
from core.ui import init_page

init_page("หน้าหลัก", "🏠")

from core.reloader import ensure_fresh

ensure_fresh()

import streamlit as st

from core import db
from core.pipeline import ALL_PERIODS_KEY
from core.ui import (
    baht,
    get_current_shop,
    load_period_result,
    render_kpi_card,
    render_page_header,
    render_section_header,
    require_login,
    summarize_for_period,
)

user = require_login()
cur_shop = get_current_shop()

skus = db.get_skus()
snapshots = db.list_snapshots(shop_code=cur_shop["code"])
latest_period = snapshots.iloc[0]["month"] if not snapshots.empty else None
active_period = st.session_state.get("period", latest_period or "-")

render_page_header(
    title="🏢 Matang Cosmetic Cost & Profit System",
    subtitle="ระบบอัตโนมัติคำนวณต้นทุนสินค้า (COGS), ค่าธรรมเนียม TikTok Shop และกำไรสุทธิแท้จริง",
    period=active_period,
)

total_periods = len(snapshots)
if not snapshots.empty and user["role"] == "admin":
    all_sales = float(snapshots["net_sales"].sum()) if "net_sales" in snapshots.columns else 0.0
    all_profit = float(snapshots["net_profit"].sum()) if "net_profit" in snapshots.columns else 0.0
else:
    all_sales = 0.0
    all_profit = 0.0

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    render_kpi_card("สินค้าในระบบทั้งหมด", f"{len(skus):,} รายการ", f"บันทึกแล้ว {total_periods:,} งวด ({cur_shop['name']})", delta="SKU Master Active", delta_positive=True, icon="📦")
with c2:
    render_kpi_card(
        f"รายได้รวมทุกงวด ({cur_shop['name']})" if total_periods > 0 else f"รายได้รวม ({cur_shop['name']})",
        baht(all_sales) if (total_periods > 0 and user["role"] == "admin") else "-",
        f"งวดล่าสุด: {latest_period or '-'}",
        delta="ยอดขายรวม" if total_periods > 0 else None,
        icon="💰",
    )
with c3:
    render_kpi_card(
        f"กำไรสุทธิรวมทุกงวด ({cur_shop['name']})" if total_periods > 0 else f"กำไรสุทธิ ({cur_shop['name']})",
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
