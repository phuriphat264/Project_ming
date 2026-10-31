"""ตัวช่วยฝั่ง Streamlit: ตัวหนังสือใหญ่ อ่านง่าย ข้อความสั้นกระชับ ใช้งานง่ายสำหรับโรงงาน"""
from __future__ import annotations

import streamlit as st

from . import db

CORPORATE_PALETTE = ["#3b82f6", "#10b981", "#6366f1", "#f59e0b", "#f43f5e", "#14b8a6", "#8b5cf6", "#64748b"]

APP_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600;700&family=Sarabun:wght@400;500;600;700&display=swap');

/* 1. ฟอนต์ภาษาไทยขนาดใหญ่ อ่านสบายตา (ไม่แตะต้อง <span> ของไอคอน) */
html, body, .stApp, p, h1, h2, h3, h4, h5, h6, label, input, textarea, button, th, td, li, a,
[data-testid="stMarkdownContainer"], [data-testid="stText"] {
    font-family: 'Prompt', 'Sarabun', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 1.06rem;
}

[data-testid="stIconMaterial"],
[data-testid*="Icon"] span,
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
}

/* 2. พื้นหลังสีพื้นสะอาดตา และขยายเต็มหน้าจอ */
.stApp {
    background-color: #f8fafc;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

.stAppDeployButton, [data-testid="stAppDeployButton"] {
    display: none !important;
}

.block-container, [data-testid="stAppViewBlockContainer"] {
    max-width: 96% !important;
    width: 96% !important;
    padding-top: 2.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2.2rem !important;
    padding-right: 2.2rem !important;
}

/* 3. เมนูด้านซ้าย (Sidebar) ตัวหนังสือใหญ่ กดง่าย */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
    min-width: 270px !important;
}

[data-testid="stSidebarNav"]::before {
    content: "มาตัง คอสเมติก\\Aระบบต้นทุนและกำไร";
    white-space: pre-wrap;
    display: block;
    padding: 14px 16px;
    margin: 6px 12px 12px 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #334155;
    border-radius: 10px;
    color: #0f172a;
    font-family: 'Prompt', 'Sarabun', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1.45;
}

[data-testid="stSidebarNavItems"] li a {
    border-radius: 10px !important;
    margin: 4px 10px !important;
    padding: 12px 16px !important;
}

[data-testid="stSidebarNavItems"] li a span {
    color: #334155 !important;
    font-weight: 500 !important;
    font-size: 1.08rem !important;
}

[data-testid="stSidebarNavItems"] li a:hover {
    background: #f1f5f9 !important;
}

[data-testid="stSidebarNavItems"] li a[aria-current="page"] {
    background: #e2e8f0 !important;
    border-left: 4px solid #1e293b !important;
}

[data-testid="stSidebarNavItems"] li a[aria-current="page"] span {
    color: #0f172a !important;
    font-weight: 700 !important;
}

/* 4. กล่องการ์ด (st.container(border=True)) โปร่ง โล่ง สบายตา */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    padding: 22px 26px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
}

/* 5. ปุ่มกดขนาดใหญ่ กดง่าย */
button[kind="primary"], [data-testid="baseButton-primary"] {
    background-color: #334155 !important;
    color: #ffffff !important;
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    padding: 0.65rem 1.4rem !important;
    min-height: 46px !important;
}

button[kind="primary"]:hover, [data-testid="baseButton-primary"]:hover {
    background-color: #1e293b !important;
    border-color: #1e293b !important;
}

button[kind="secondary"], [data-testid="baseButton-secondary"] {
    background-color: #ffffff !important;
    color: #1e293b !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
    font-size: 1.02rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.2rem !important;
    min-height: 44px !important;
}

button[kind="secondary"]:hover, [data-testid="baseButton-secondary"]:hover {
    background-color: #f1f5f9 !important;
    border-color: #94a3b8 !important;
}

/* 6. ช่องกรอกข้อมูลและป้ายชื่อตัวใหญ่ */
.stTextInput label p, .stNumberInput label p, .stSelectbox label p, .stSlider label p {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #1e293b !important;
}

.stTextInput input, .stNumberInput input {
    font-size: 1.08rem !important;
    padding: 0.6rem 0.8rem !important;
}

/* 7. แท็บ (Tabs) ตัวหนังสือใหญ่ */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: #e2e8f0;
    padding: 6px;
    border-radius: 12px;
    margin-bottom: 16px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 9px;
    padding: 10px 24px;
    font-size: 1.05rem !important;
    font-weight: 600;
    color: #475569;
    border: none;
    background: transparent;
}

.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #0f172a !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
</style>
"""


def init_page(title: str, icon: str = "📊") -> None:
    st.set_page_config(page_title=f"{title} | มาตัง คอสเมติก", page_icon=icon, layout="wide")
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)
    db.init_db()
    if st.session_state.get("_reset_v") != 7:
        for k in ("result", "period", "raw", "notes"):
            st.session_state.pop(k, None)
        st.session_state["_reset_v"] = 7


def render_page_header(
    title: str,
    subtitle: str = "",
    badge_text: str = "",
    badge_color: str = "slate",
    period: str | None = None,
) -> None:
    """หัวข้อหน้าจอขนาดใหญ่ อ่านง่าย ไม่รก"""
    period_html = ""
    if period:
        period_html = (
            f'<div style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:10px;padding:8px 18px;text-align:right;">'
            f'<span style="font-size:0.9rem;color:#475569;">งวดบัญชี: </span>'
            f'<b style="font-size:1.25rem;color:#0f172a;">{period}</b>'
            f"</div>"
        )

    sub_html = f'<div style="font-size:1.05rem;color:#64748b;margin-top:4px;">{subtitle}</div>' if subtitle else ""

    html = (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-left:6px solid #334155;'
        f'border-radius:14px;padding:20px 26px;margin-bottom:20px;display:flex;justify-content:space-between;'
        f'align-items:center;flex-wrap:wrap;gap:14px;">'
        f"<div>"
        f'<div style="font-size:1.85rem;font-weight:700;color:#0f172a;line-height:1.25;">{title}</div>'
        f"{sub_html}"
        f"</div>"
        f"{period_html}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    delta: str | None = None,
    delta_positive: bool | None = True,
    accent: str = "slate",
    icon: str = "📊",
) -> None:
    """การ์ดตัวเลขขนาดใหญ่ ชัดเจน อ่านง่ายในพริบตา"""
    badge_html = ""
    if delta:
        if delta_positive is True:
            d_bg, d_fg = "#dcfce7", "#166534"
        elif delta_positive is False:
            d_bg, d_fg = "#fee2e2", "#991b1b"
        else:
            d_bg, d_fg = "#f1f5f9", "#334155"
        badge_html = (
            f'<span style="background:{d_bg};color:{d_fg};font-size:0.92rem;font-weight:600;'
            f'padding:3px 10px;border-radius:8px;">{delta}</span>'
        )

    sub_html = f'<span style="font-size:0.95rem;color:#64748b;">{subtitle}</span>' if subtitle else ""

    html = (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:20px 22px;'
        f'margin-bottom:14px;min-height:132px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="font-size:1.05rem;font-weight:600;color:#475569;">{icon} {title}</div>'
        f'<div style="font-size:2.05rem;font-weight:700;color:#0f172a;margin:8px 0;">{value}</div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">{badge_html}{sub_html}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = "", icon: str = "📌") -> None:
    """หัวข้อส่วนย่อย ตัวใหญ่ กระชับ"""
    html = (
        f'<div style="font-size:1.3rem;font-weight:700;color:#0f172a;margin:6px 0 14px 0;">'
        f"{icon} {title}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def style_plotly(fig, height: int = 360):
    """ปรับกราฟให้ทันสมัย คมชัด สวยงามสไตล์ Modern Financial Dashboard"""
    fig.update_layout(
        font=dict(family="Prompt, Sarabun, sans-serif", size=14, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(t=28, b=24, l=16, r=24),
        hoverlabel=dict(
            bgcolor="#0f172a",
            bordercolor="#0f172a",
            font=dict(family="Prompt, Sarabun, sans-serif", size=14, color="#ffffff"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=13.5, color="#334155"),
            bgcolor="rgba(255,255,255,0)",
        ),
        xaxis=dict(
            showgrid=False,
            linecolor="#e2e8f0",
            tickfont=dict(size=13, color="#475569"),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor="#e2e8f0",
            griddash="dot",
            linecolor="rgba(0,0,0,0)",
            tickfont=dict(size=13, color="#475569"),
            zeroline=True,
            zerolinecolor="#cbd5e1",
            zerolinewidth=1.5,
        ),
    )
    return fig


def login_form() -> None:
    """หน้าล็อกอินเรียบง่าย ตัวหนังสือใหญ่"""
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                '<div style="margin-bottom:18px;">'
                '<div style="font-size:1.65rem;font-weight:700;color:#0f172a;">🔐 เข้าสู่ระบบ</div>'
                '<div style="font-size:1.02rem;color:#64748b;margin-top:4px;">บริษัท มาตัง คอสเมติก จำกัด</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                user = st.text_input("ชื่อผู้ใช้", placeholder="admin หรือ staff")
                pw = st.text_input("รหัสผ่าน", type="password", placeholder="••••••••")
                remember = st.checkbox("จดจำการเข้าสู่ระบบบนเครื่องนี้ (ไม่ต้องกรอกใหม่รอบหน้า)", value=True)
                if st.form_submit_button("เข้าสู่ระบบ", type="primary", width="stretch"):
                    info = db.verify_user(user, pw)
                    if info:
                        st.session_state["user"] = info
                        if remember:
                            db.save_remembered_user(info["username"])
                        else:
                            db.clear_remembered_user()
                        st.rerun()
                    else:
                        st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

            st.caption("บัญชีทดสอบ: ผู้บริหาร `admin / admin123` · พนักงาน `staff / staff123`")


def current_user() -> dict | None:
    u = st.session_state.get("user")
    if u:
        return u
    remembered = db.get_remembered_user()
    if remembered:
        st.session_state["user"] = remembered
        return remembered
    return None


def require_login(admin_only: bool = False) -> dict:
    user = current_user()
    if not user:
        login_form()
        st.stop()

    with st.sidebar:
        role_label = "ผู้บริหาร (Admin)" if user["role"] == "admin" else "พนักงาน (Staff)"
        st.markdown(
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
            f'<div style="font-weight:700;font-size:1.08rem;color:#0f172a;">👤 {user["display_name"]}</div>'
            f'<div style="font-size:0.92rem;color:#475569;margin-top:2px;">{role_label}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.get("result") is not None:
            if st.button("🔄 ล้างข้อมูลที่เปิดอยู่", width="stretch", type="secondary"):
                for k in ("result", "period", "raw", "notes"):
                    st.session_state.pop(k, None)
                st.rerun()

        if st.button("ออกจากระบบ", width="stretch", type="secondary"):
            db.clear_remembered_user()
            st.session_state.clear()
            st.rerun()

    if admin_only and user["role"] != "admin":
        st.warning("🔒 หน้านี้สำหรับผู้บริหารหรือฝ่ายบัญชีเท่านั้น")
        st.stop()

    return user


def is_admin() -> bool:
    u = current_user()
    return bool(u and u["role"] == "admin")


def _snapshot_to_pipeline_result(loaded: dict):
    import pandas as pd
    from core.pipeline import PipelineResult

    return PipelineResult(
        orders=loaded["orders"],
        order_lines=loaded["lines"],
        ads=loaded["ads"],
        missing_skus=pd.DataFrame(),
        source=loaded["source"],
        warnings=loaded["warnings"],
        fee_details=loaded.get("fee_details", {}),
        withdrawals=loaded.get("withdrawals", pd.DataFrame()),
    )


def _distinct_saved_months(months: list[str]) -> list[str]:
    """เรียงให้งวดแยกรายร้านมาก่อนงวด '(รวม)' เพื่อเวลาดึงสรุปทั้งหมดจะได้ไม่ซ้ำซ้อน"""
    non_merged = [m for m in months if "(รวม)" not in m]
    merged_only = [m for m in months if "(รวม)" in m]
    return non_merged + merged_only


def load_period_result(period: str):
    """โหลดข้อมูล PipelineResult ของงวดเดี่ยว หรือรวมทุกงวดทั้งหมด (ALL_PERIODS_KEY)"""
    from core.pipeline import ALL_PERIODS_KEY, combine_pipeline_results, recalculate_with_skus

    sku_master = db.get_skus()
    if period == ALL_PERIODS_KEY:
        snaps = db.list_snapshots()
        if snaps.empty:
            return None
        ordered_months = _distinct_saved_months(snaps["month"].tolist())
        loaded_list = []
        for m in ordered_months:
            ld = db.load_snapshot(m)
            if ld:
                loaded_list.append(_snapshot_to_pipeline_result(ld))
        if not loaded_list:
            return None
        return combine_pipeline_results(loaded_list, sku_master)

    loaded = db.load_snapshot(period)
    if not loaded:
        return None
    return recalculate_with_skus(_snapshot_to_pipeline_result(loaded), sku_master)


def get_period_financial_params(period: str) -> tuple[float, float, float | None]:
    """คืนค่า (fixed_costs_total, comm_pct, override_sales_commission) รองรับทั้งงวดเดียวและรวมทุกงวด"""
    from core.metrics import summarize
    from core.pipeline import ALL_PERIODS_KEY, build_order_row_keys, recalculate_with_skus

    if period != ALL_PERIODS_KEY:
        return db.total_fixed_cost(period), db.get_comm_pct(period), None

    snaps = db.list_snapshots()
    if snaps.empty:
        return 0.0, 0.0, 0.0

    sku_master = db.get_skus()
    ordered_months = _distinct_saved_months(snaps["month"].tolist())
    seen_orders: set[tuple] = set()
    total_fixed = 0.0
    total_comm = 0.0
    total_rough_pos = 0.0

    for m in ordered_months:
        ld = db.load_snapshot(m)
        if not ld:
            continue
        r_m = recalculate_with_skus(_snapshot_to_pipeline_result(ld), sku_master)
        keys = set(build_order_row_keys(r_m.orders))
        # ข้ามงวด '(รวม)' ถ้าออเดอร์ทั้งหมดอยู่ในงวดย่อยที่นับไปแล้ว
        if keys and keys.issubset(seen_orders):
            continue
        seen_orders.update(keys)

        fc_m = db.total_fixed_cost(m)
        cp_m = db.get_comm_pct(m)
        s_m = summarize(r_m, fixed_costs=fc_m, comm_pct=cp_m)
        total_fixed += fc_m
        total_comm += s_m.sales_commission
        if s_m.rough_profit > 0:
            total_rough_pos += s_m.rough_profit

    eff_pct = (total_comm / total_rough_pos * 100.0) if total_rough_pos > 0 and total_comm > 0 else 0.0
    return total_fixed, eff_pct, total_comm


def summarize_for_period(res, period: str):
    """คำนวณ Summary สำหรับงวดที่เลือก (รองรับทั้งงวดรายเดือนและสรุปรวมทุกงวดทั้งหมด)"""
    from core.metrics import summarize

    fixed_total, comm_pct, override_comm = get_period_financial_params(period)
    return summarize(
        res,
        fixed_costs=fixed_total,
        comm_pct=comm_pct,
        override_sales_commission=override_comm,
    )


def build_saved_periods_comparison_df():
    """สร้างตารางเปรียบเทียบผลประกอบการของทุกงวดที่บันทึกไว้ในระบบ (เรียงจากเดือนเก่าไปใหม่)"""
    import pandas as pd
    from core.metrics import monthly_comparison_table, summarize
    from core.pipeline import recalculate_with_skus

    snaps = db.list_snapshots()
    if snaps.empty:
        return pd.DataFrame()

    sku_master = db.get_skus()
    months_asc = sorted(snaps["month"].tolist())
    rows = []
    for m in months_asc:
        ld = db.load_snapshot(m)
        if not ld:
            continue
        r_m = recalculate_with_skus(_snapshot_to_pipeline_result(ld), sku_master)
        s_m = summarize(r_m, fixed_costs=db.total_fixed_cost(m), comm_pct=db.get_comm_pct(m))
        rows.append((m, s_m))
    return monthly_comparison_table(rows)


def render_period_selector(container=None, key: str = "global_period_sel") -> str:
    """กล่องเลือกสลับดู 'สรุปรวมทุกงวดทั้งหมด' หรือ 'แยกดูแต่ละเดือน' ใช้ร่วมกันทุกหน้า"""
    from core.pipeline import ALL_PERIODS_KEY

    host = container if container is not None else st
    snaps = db.list_snapshots()
    cur_period = st.session_state.get("period", "")

    if snaps.empty:
        return cur_period

    saved_months = snaps["month"].tolist()
    order_map = dict(zip(snaps["month"], snaps["order_count"]))
    options = [ALL_PERIODS_KEY] + saved_months
    if cur_period and cur_period not in options:
        options.insert(1, cur_period)

    idx = options.index(cur_period) if cur_period in options else 0

    def _fmt(opt: str) -> str:
        if opt == ALL_PERIODS_KEY:
            return f"📊 สรุปรวมทุกงวดทั้งหมด ({len(saved_months)} งวด)"
        cnt = order_map.get(opt)
        return f"📅 งวด {opt} ({int(cnt):,} ออเดอร์)" if cnt is not None else f"📅 งวด {opt} (ยังไม่บันทึก)"

    selected = host.selectbox(
        "📅 เลือกดูข้อมูล (แยกตามเดือน หรือ สรุปรวมทุกงวดทั้งหมด):",
        options,
        index=idx,
        format_func=_fmt,
        key=key,
    )
    if selected != cur_period:
        new_res = load_period_result(selected)
        if new_res is not None:
            db.set_app_state("active_period", selected)
            st.session_state.update(result=new_res, period=selected, notes=[])
            st.rerun()
    return selected


def require_result():
    from core.pipeline import ALL_PERIODS_KEY, recalculate_with_skus

    res = st.session_state.get("result")
    cur_period = st.session_state.get("period")

    if res is None:
        snaps = db.list_snapshots()
        if not snaps.empty:
            saved_p = db.get_app_state("active_period")
            months = snaps["month"].tolist()
            if saved_p == ALL_PERIODS_KEY:
                target_period = ALL_PERIODS_KEY
            elif saved_p and saved_p in months:
                target_period = saved_p
            else:
                target_period = months[0]
            loaded_res = load_period_result(target_period)
            if loaded_res is not None:
                st.session_state.update(result=loaded_res, period=target_period, notes=[])
                return loaded_res
        st.info("กรุณาไปที่หน้า **📤 นำเข้าข้อมูล** เพื่ออัปโหลดไฟล์ Excel ก่อน")
        st.page_link("pages/2_📤_นำเข้าข้อมูล.py", label="ไปหน้านำเข้าข้อมูล", icon="📤")
        st.stop()

    # ถ้านั่งดูสรุปรวมทุกงวดทั้งหมด ให้โหลดรวมใหม่อัตโนมัติเผื่อเพิ่งอัปเดต SKU หรือเพิ่ม/ลบงวด
    if cur_period == ALL_PERIODS_KEY:
        refreshed = load_period_result(ALL_PERIODS_KEY)
        if refreshed is not None:
            st.session_state["result"] = refreshed
            return refreshed

    # คำนวณต้นทุนใหม่เสมอเผื่อผู้ใช้เพิ่งเพิ่ม/ลบ/แก้ไขราคาทุน SKU ในฐานข้อมูล
    res = recalculate_with_skus(res, db.get_skus())
    st.session_state["result"] = res
    return res


def baht(v: float | None) -> str:
    return "-" if v is None else f"฿{v:,.0f}"
