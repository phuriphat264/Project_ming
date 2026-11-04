"""ตัวช่วยฝั่ง Streamlit: ตัวหนังสือใหญ่ อ่านง่าย ข้อความสั้นกระชับ ใช้งานง่ายสำหรับโรงงาน"""
from __future__ import annotations

import streamlit as st

from . import db

CORPORATE_PALETTE = ["#4f46e5", "#10b981", "#06b6d4", "#f59e0b", "#f43f5e", "#8b5cf6", "#ec4899", "#64748b"]

APP_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Prompt:wght@300;400;500;600;700;800&display=swap');

/* 1. ฟอนต์ภาษาไทยและอังกฤษ Modern Luxury SaaS */
html, body, .stApp, p, h1, h2, h3, h4, h5, h6, label, input, textarea, button, th, td, li, a,
[data-testid="stMarkdownContainer"], [data-testid="stText"] {
    font-family: 'Plus Jakarta Sans', 'Prompt', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 1.04rem;
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

/* 2. พื้นหลัง Mesh Gradient สะอาดตา พรีเมียม */
.stApp {
    background-color: #f8fafc;
    background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.05) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(14, 165, 233, 0.04) 0px, transparent 50%),
        radial-gradient(at 50% 50%, rgba(241, 245, 249, 0.5) 0px, transparent 100%);
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

.stAppDeployButton, [data-testid="stAppDeployButton"] {
    display: none !important;
}

.block-container, [data-testid="stAppViewBlockContainer"] {
    max-width: 95% !important;
    width: 95% !important;
    padding-top: 2.0rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 2.2rem !important;
    padding-right: 2.2rem !important;
}

/* 3. เมนูด้านซ้าย (Sidebar) สไตล์ Modern Dark Navy & Violet */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 50%, #1e1b4b 100%) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    min-width: 280px !important;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15) !important;
}

[data-testid="stSidebarNav"]::before {
    content: "✨ MATANG COSMETIC\\Aระบบต้นทุนและกำไร TikTok";
    white-space: pre-wrap;
    display: block;
    padding: 16px 18px;
    margin: 10px 14px 16px 14px;
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.28) 0%, rgba(147, 51, 234, 0.22) 100%);
    border: 1px solid rgba(165, 180, 252, 0.35);
    border-radius: 14px;
    color: #ffffff;
    font-family: 'Plus Jakarta Sans', 'Prompt', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    line-height: 1.45;
    letter-spacing: 0.01em;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.25);
}

[data-testid="stSidebarNavItems"] li a {
    border-radius: 12px !important;
    margin: 4px 12px !important;
    padding: 12px 18px !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

[data-testid="stSidebarNavItems"] li a span {
    color: #cbd5e1 !important;
    font-weight: 500 !important;
    font-size: 1.06rem !important;
}

[data-testid="stSidebarNavItems"] li a:hover {
    background: rgba(255, 255, 255, 0.08) !important;
    transform: translateX(4px);
}

[data-testid="stSidebarNavItems"] li a:hover span {
    color: #ffffff !important;
}

[data-testid="stSidebarNavItems"] li a[aria-current="page"] {
    background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.42) !important;
    border: 1px solid rgba(199, 210, 254, 0.3) !important;
}

[data-testid="stSidebarNavItems"] li a[aria-current="page"] span {
    color: #ffffff !important;
    font-weight: 700 !important;
}

/* 4. กล่องการ์ด (st.container(border=True)) สไตล์ Frosted Glass Card */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important;
    border: 1px solid rgba(226, 232, 240, 0.85) !important;
    border-radius: 18px !important;
    padding: 24px 28px !important;
    box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04), 0 2px 6px -1px rgba(15, 23, 42, 0.02) !important;
    transition: all 0.2s ease;
}

/* 5. ปุ่มกด Modern Gradient & Sleek Button */
button[kind="primary"], [data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    padding: 0.72rem 1.6rem !important;
    min-height: 48px !important;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.32) !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.01em;
}

button[kind="primary"]:hover, [data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #4338ca 0%, #4f46e5 100%) !important;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(79, 70, 229, 0.45) !important;
}

button[kind="secondary"], [data-testid="baseButton-secondary"] {
    background-color: #ffffff !important;
    color: #1e293b !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 12px !important;
    font-size: 1.02rem !important;
    font-weight: 600 !important;
    padding: 0.65rem 1.35rem !important;
    min-height: 46px !important;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03) !important;
    transition: all 0.2s ease !important;
}

button[kind="secondary"]:hover, [data-testid="baseButton-secondary"]:hover {
    background-color: #f8fafc !important;
    border-color: #94a3b8 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06) !important;
}

/* 6. ช่องกรอกข้อมูลและป้ายชื่อ */
.stTextInput label p, .stNumberInput label p, .stSelectbox label p, .stSlider label p, .stMultiSelect label p {
    font-size: 1.02rem !important;
    font-weight: 600 !important;
    color: #1e293b !important;
    letter-spacing: 0.01em;
}

.stTextInput input, .stNumberInput input {
    font-size: 1.06rem !important;
    padding: 0.65rem 0.95rem !important;
    border-radius: 12px !important;
    border: 1px solid #cbd5e1 !important;
    background-color: #ffffff !important;
    transition: all 0.2s ease !important;
}

.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
}

/* 7. แท็บ (Tabs) สไตล์ Segmented Floating Pill */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: #f1f5f9;
    padding: 6px;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    margin-bottom: 20px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: 10px 22px;
    font-size: 1.02rem !important;
    font-weight: 600;
    color: #64748b;
    border: none;
    background: transparent;
    transition: all 0.2s ease;
}

.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #4f46e5 !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08) !important;
}

/* 8. ตาราง DataFrame */
[data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.02) !important;
}

/* 9. กรอบอัปโหลดไฟล์ */
[data-testid="stFileUploader"] {
    border-radius: 14px !important;
}
</style>
"""


def init_page(title: str, icon: str = "📊") -> None:
    st.set_page_config(page_title=f"{title} | มาตัง คอสเมติก", page_icon=icon, layout="wide")
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(APP_THEME_CSS, unsafe_allow_html=True)
    if not st.session_state.get("_db_inited"):
        db.init_db()
        st.session_state["_db_inited"] = True
    if st.session_state.get("_reset_v") != 7:
        for k in ("result", "period", "raw", "notes"):
            st.session_state.pop(k, None)
        st.session_state["_reset_v"] = 7


def get_current_shop() -> dict:
    """ดึงข้อมูลร้านค้าที่ผู้ใช้กำลังเลือกใช้งานอยู่ในระบบ (Session) หรือค่าเริ่มต้น"""
    shops = db.list_shops(active_only=True)
    if not shops:
        return {"code": "matang", "name": "มาตัง (Matang)", "tiktok_handle": "@matang_official", "is_default": 1}

    cur_code = st.session_state.get("active_shop_code")
    if cur_code:
        found = next((s for s in shops if s["code"] == cur_code), None)
        if found:
            return found

    def_shop = next((s for s in shops if s.get("is_default")), shops[0])
    st.session_state["active_shop_code"] = def_shop["code"]
    return def_shop


def set_current_shop(code: str) -> None:
    """กำหนดรหัสร้านค้าที่กำลังเลือกใช้งานอยู่"""
    st.session_state["active_shop_code"] = code
    st.session_state["global_upload_shop_select"] = code


def render_page_header(
    title: str,
    subtitle: str = "",
    badge_text: str = "",
    badge_color: str = "slate",
    period: str | None = None,
    show_shop: bool = True,
    shop: dict | None = None,
) -> None:
    """หัวข้อหน้าจอขนาดใหญ่ สไตล์ Modern Executive Banner พร้อมแสดงร้านค้าและงวดบัญชีที่เลือก"""
    badges_html = []

    if show_shop:
        c_shop = shop or get_current_shop()
        s_name = c_shop.get("name", "มาตัง (Matang)")
        s_handle = f" {c_shop.get('tiktok_handle')}" if c_shop.get("tiktok_handle") else ""
        s_badge = "★ ร้านหลัก" if c_shop.get("is_default") else "ร้านย่อย"
        shop_html = (
            f'<div style="background:linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);border:1px solid #c7d2fe;'
            f'border-radius:14px;padding:9px 18px;text-align:right;box-shadow:0 2px 10px rgba(99, 102, 241, 0.12);">'
            f'<div style="font-size:0.80rem;font-weight:700;color:#4338ca;display:flex;align-items:center;justify-content:flex-end;gap:6px;">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#6366f1;box-shadow:0 0 6px #6366f1;"></span>'
            f'🏬 ร้านค้าที่เลือก ({s_badge})</div>'
            f'<b style="font-size:1.20rem;font-weight:800;color:#1e1b4b;letter-spacing:-0.01em;">{s_name}{s_handle}</b>'
            f'</div>'
        )
        badges_html.append(shop_html)

    if period:
        period_html = (
            f'<div style="background:linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);border:1px solid #a7f3d0;'
            f'border-radius:14px;padding:9px 18px;text-align:right;box-shadow:0 2px 10px rgba(16, 185, 129, 0.12);">'
            f'<div style="font-size:0.80rem;font-weight:700;color:#047857;display:flex;align-items:center;justify-content:flex-end;gap:6px;">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#10b981;box-shadow:0 0 6px #10b981;"></span>'
            f'📅 งวดบัญชีที่เลือก</div>'
            f'<b style="font-size:1.20rem;font-weight:800;color:#064e3b;letter-spacing:-0.01em;">{period}</b>'
            f'</div>'
        )
        badges_html.append(period_html)

    right_col = f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">{"".join(badges_html)}</div>' if badges_html else ""
    sub_html = f'<div style="font-size:1.02rem;color:#64748b;margin-top:6px;font-weight:400;">{subtitle}</div>' if subtitle else ""

    html = (
        f'<div style="background:linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);border:1px solid rgba(226, 232, 240, 0.9);'
        f'border-radius:18px;padding:22px 28px;margin-bottom:24px;display:flex;justify-content:space-between;'
        f'align-items:center;flex-wrap:wrap;gap:16px;box-shadow:0 4px 20px -2px rgba(15, 23, 42, 0.05);">'
        f"<div>"
        f'<div style="font-size:1.95rem;font-weight:800;color:#0f172a;line-height:1.25;letter-spacing:-0.02em;">{title}</div>'
        f"{sub_html}"
        f"</div>"
        f"{right_col}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    delta: str | None = None,
    delta_positive: bool | None = True,
    accent: str = "indigo",
    icon: str = "📊",
) -> None:
    """การ์ดตัวเลขขนาดใหญ่ สไตล์ FinTech Glassmorphism พร้อม Badge สวยงาม"""
    badge_html = ""
    if delta:
        if delta_positive is True:
            d_bg, d_fg, d_bd = "#ecfdf5", "#065f46", "#a7f3d0"
            d_icon = "▲"
        elif delta_positive is False:
            d_bg, d_fg, d_bd = "#fff1f2", "#9f1239", "#fecdd3"
            d_icon = "▼"
        else:
            d_bg, d_fg, d_bd = "#f1f5f9", "#334155", "#cbd5e1"
            d_icon = "●"
        badge_html = (
            f'<span style="background:{d_bg};color:{d_fg};border:1px solid {d_bd};font-size:0.86rem;font-weight:700;'
            f'padding:3px 10px;border-radius:8px;display:inline-flex;align-items:center;gap:4px;">'
            f'<span style="font-size:0.75rem;">{d_icon}</span> {delta}</span>'
        )

    sub_html = f'<span style="font-size:0.92rem;color:#64748b;font-weight:500;">{subtitle}</span>' if subtitle else ""

    html = (
        f'<div style="background:#ffffff;border:1px solid rgba(226, 232, 240, 0.9);border-radius:18px;padding:22px 24px;'
        f'margin-bottom:16px;min-height:142px;display:flex;flex-direction:column;justify-content:space-between;'
        f'box-shadow:0 4px 18px -2px rgba(15, 23, 42, 0.04);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="font-size:0.98rem;font-weight:700;color:#475569;letter-spacing:0.01em;">{title}</div>'
        f'<div style="width:38px;height:38px;border-radius:12px;background:rgba(99, 102, 241, 0.08);color:#4f46e5;display:flex;align-items:center;justify-content:center;font-size:1.25rem;">{icon}</div>'
        f'</div>'
        f'<div style="font-size:2.2rem;font-weight:800;color:#0f172a;letter-spacing:-0.03em;margin:10px 0 6px 0;">{value}</div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">{badge_html}{sub_html}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = "", icon: str = "📌") -> None:
    """หัวข้อส่วนย่อย สไตล์ Minimalist Gradient Indicator"""
    sub_html = f'<div style="font-size:0.95rem;color:#64748b;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    html = (
        f'<div style="display:flex;align-items:center;gap:12px;margin:12px 0 16px 0;">'
        f'<div style="width:4px;height:24px;border-radius:4px;background:linear-gradient(180deg, #4f46e5 0%, #7c3aed 100%);"></div>'
        f'<div><div style="font-size:1.32rem;font-weight:800;color:#0f172a;letter-spacing:-0.01em;">{icon} {title}</div>{sub_html}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def style_plotly(fig, height: int = 360):
    """ปรับกราฟให้ทันสมัย คมชัด สวยงามสไตล์ Modern Financial Dashboard"""
    fig.update_layout(
        font=dict(family="Plus Jakarta Sans, Prompt, sans-serif", size=13.5, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(t=28, b=24, l=16, r=24),
        hoverlabel=dict(
            bgcolor="#0f172a",
            bordercolor="#0f172a",
            font=dict(family="Plus Jakarta Sans, Prompt, sans-serif", size=13.5, color="#ffffff"),
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
    """หน้าล็อกอินสไตล์ Modern SaaS Portal"""
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)
    st.markdown("<div style='height: 48px;'></div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.25, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                '<div style="text-align:center;margin-bottom:24px;">'
                '<div style="width:56px;height:56px;margin:0 auto 14px auto;border-radius:16px;background:linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);color:white;display:flex;align-items:center;justify-content:center;font-size:1.75rem;box-shadow:0 6px 20px rgba(79,70,229,0.35);">🔐</div>'
                '<div style="font-size:1.75rem;font-weight:800;color:#0f172a;letter-spacing:-0.02em;">เข้าสู่ระบบ</div>'
                '<div style="font-size:0.96rem;color:#64748b;margin-top:4px;font-weight:500;">บริษัท มาตัง คอสเมติก จำกัด · Cost & Profit Intelligence</div>'
                "</div>",
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                user = st.text_input("ชื่อผู้ใช้", placeholder="admin หรือ staff")
                pw = st.text_input("รหัสผ่าน", type="password", placeholder="••••••••")
                remember = st.checkbox("จดจำการเข้าสู่ระบบบนเครื่องนี้", value=True)
                if st.form_submit_button("🚀 เข้าสู่ระบบทันที", type="primary", width="stretch"):
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
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin-bottom:10px;">'
            f'<div style="font-weight:700;font-size:1.08rem;color:#0f172a;">👤 {user["display_name"]}</div>'
            f'<div style="font-size:0.92rem;color:#475569;margin-top:2px;">{role_label}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # การ์ดแสดงร้านค้าที่กำลังเลือกใช้งานอยู่
        c_shop = get_current_shop()
        all_act_shops = db.list_shops(active_only=True)
        s_codes = [s["code"] for s in all_act_shops]
        s_map = {s["code"]: s for s in all_act_shops}

        def _fmt_side_shop(c: str) -> str:
            item = s_map.get(c, {})
            star = " ★" if item.get("is_default") else ""
            return f"🏬 {item.get('name', c)}{star}"

        b_star = "★ ร้านหลัก" if c_shop.get("is_default") else "ร้านย่อย"
        h_txt = f" ({c_shop.get('tiktok_handle')})" if c_shop.get("tiktok_handle") else ""

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                        border: 1px solid #4338ca; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
                        box-shadow: 0 4px 14px rgba(49, 46, 129, 0.25); color: white;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;">
                    <span style="font-size: 0.74rem; font-weight: 700; color: #a5b4fc; text-transform: uppercase; letter-spacing: 0.05em;">
                        🏬 ร้านค้าที่เลือกอยู่
                    </span>
                    <span style="background: rgba(165, 180, 252, 0.25); border: 1px solid rgba(165, 180, 252, 0.5);
                                 color: #e0e7ff; font-size: 0.68rem; font-weight: 700; padding: 1px 7px; border-radius: 999px;">
                        {b_star}
                    </span>
                </div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #ffffff; line-height: 1.25;">
                    {c_shop.get('name')}{h_txt}
                </div>
                <div style="font-size: 0.75rem; color: #c7d2fe; margin-top: 4px;">
                    รหัสร้าน: <code style="background: rgba(0,0,0,0.3); color: #fbcfe8; padding: 1px 5px; border-radius: 4px; font-weight: 600;">{c_shop.get('code')}</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if len(all_act_shops) > 1:
            cur_idx = s_codes.index(c_shop["code"]) if c_shop["code"] in s_codes else 0
            sel_side_shop = st.selectbox(
                "🔄 สลับเลือกร้านค้า:",
                options=s_codes,
                index=cur_idx,
                format_func=_fmt_side_shop,
                key="sidebar_active_shop_dropdown",
                help="เลือกเพื่อสลับร้านค้าที่ต้องการดูหรือนำเข้าข้อมูล",
            )
            if sel_side_shop != c_shop["code"]:
                set_current_shop(sel_side_shop)
                st.rerun()

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
        raw_settlement=loaded.get("raw_settlement", pd.DataFrame()),
        raw_orders=loaded.get("raw_orders", pd.DataFrame()),
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


_COMP_DF_CACHE: tuple[str, pd.DataFrame] | None = None


def build_saved_periods_comparison_df():
    """สร้างตารางเปรียบเทียบผลประกอบการของทุกงวดที่บันทึกไว้ในระบบ (มีแคชรวดเร็วระดับเสี้ยววินาที)"""
    global _COMP_DF_CACHE
    import pandas as pd
    from core.metrics import monthly_comparison_table, summarize
    from core.pipeline import recalculate_with_skus

    snaps = db.list_snapshots()
    if snaps.empty:
        return pd.DataFrame()

    sku_master = db.get_skus()
    cache_sig = f"{','.join(snaps['month'].tolist())}_{len(sku_master)}"
    if _COMP_DF_CACHE is not None and _COMP_DF_CACHE[0] == cache_sig:
        return _COMP_DF_CACHE[1].copy()

    months_asc = sorted(snaps["month"].tolist())
    rows = []
    for m in months_asc:
        ld = db.load_snapshot(m)
        if not ld:
            continue
        r_m = recalculate_with_skus(_snapshot_to_pipeline_result(ld), sku_master)
        s_m = summarize(r_m, fixed_costs=db.total_fixed_cost(m), comm_pct=db.get_comm_pct(m))
        rows.append((m, s_m))
    res = monthly_comparison_table(rows)
    _COMP_DF_CACHE = (cache_sig, res)
    return res.copy()


def render_period_selector(container=None, key: str = "global_period_sel") -> str:
    """กล่องเลือกสลับดู 'สรุปรวมทุกงวดทั้งหมด' หรือ 'แยกดูแต่ละเดือน / แต่ละช่องทาง' ใช้ร่วมกันทุกหน้า"""
    from core.pipeline import ALL_PERIODS_KEY

    host = container if container is not None else st
    snaps = db.list_snapshots()
    cur_period = st.session_state.get("period", "")

    if snaps.empty:
        if key in st.session_state:
            st.session_state.pop(key, None)
        return cur_period

    saved_months = snaps["month"].tolist()
    order_map = dict(zip(snaps["month"], snaps["order_count"]))

    # กำหนด options ตามจำนวนงวดจริงในฐานข้อมูล
    if len(saved_months) >= 2:
        options = [ALL_PERIODS_KEY] + saved_months
    else:
        options = saved_months

    # ถ้าคีย์ widget ใน session_state ไม่อยู่ใน options แล้ว ให้ลบทันที ป้องกันค้างงวดที่ถูกลบ
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state.pop(key, None)

    # ถ้างวดปัจจุบันไม่อยู่ใน options ให้รีเซ็ตไปยังงวดที่ถูกต้องทันที
    if cur_period not in options:
        cur_period = options[0]
        st.session_state["period"] = cur_period
        new_res = load_period_result(cur_period)
        if new_res is not None:
            db.set_app_state("active_period", cur_period)
            st.session_state["result"] = new_res

    idx = options.index(cur_period) if cur_period in options else 0

    shops_map = {s["code"]: s["name"] for s in db.list_shops()}
    shop_code_map = dict(zip(snaps["month"], snaps["shop_code"])) if "shop_code" in snaps.columns else {}

    def _fmt(opt: str) -> str:
        if opt == ALL_PERIODS_KEY:
            return f"📊 สรุปรวมทุกงวดและทุกช่องทาง ({len(saved_months)} งวด)"
        cnt = order_map.get(opt)
        cnt_str = f"({int(cnt):,} ออเดอร์)" if cnt is not None else "(ยังไม่บันทึก)"
        if "(รวม)" in opt or "(รวมทุกงวด)" in opt:
            return f"📈 [รวมทุกช่องทาง] {opt} {cnt_str}"
        s_c = shop_code_map.get(opt, "")
        s_name = shops_map.get(s_c, "")
        if s_name:
            return f"🏬 [{s_name}] {opt} {cnt_str}"
        elif "(" in opt and ")" in opt:
            return f"🏬 {opt} {cnt_str}"
        return f"🏬 งวด {opt} {cnt_str}"

    selected = host.selectbox(
        "📅 เลือกดูข้อมูล (แยกตามเดือน / ช่องทาง หรือ สรุปรวมทุกงวดทั้งหมด):",
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


def build_channel_comparison_df(period_filter: str | None = None) -> pd.DataFrame:
    """ดึงและคำนวณเปรียบเทียบผลประกอบการแยกตามแต่ละช่องทาง TikTok Shop"""
    import pandas as pd
    from core.metrics import summarize
    from core.pipeline import ALL_PERIODS_KEY, recalculate_with_skus

    snaps = db.list_snapshots()
    if snaps.empty:
        return pd.DataFrame()

    sku_master = db.get_skus()
    rows = []
    target_snaps = snaps.copy()
    if period_filter and period_filter != ALL_PERIODS_KEY:
        base_m = period_filter.split()[0]
        target_snaps = target_snaps[target_snaps["month"].str.startswith(base_m)]

    # ข้ามงวด (รวม) เพื่อไม่ให้นับตัวเลขซ้ำ
    non_merged = target_snaps[~target_snaps["month"].str.contains(r"\(รวม\)")].copy()
    if non_merged.empty:
        non_merged = target_snaps

    shops_map = {s["code"]: s["name"] for s in db.list_shops()}

    for _, row in non_merged.iterrows():
        m = row["month"]
        ld = db.load_snapshot(m)
        if not ld:
            continue
        r_m = recalculate_with_skus(_snapshot_to_pipeline_result(ld), sku_master)
        s_code = ld.get("shop_code") or "matang"
        shop_title = shops_map.get(s_code) or ("ดีไวน์ (Dwine)" if "ดีไวน์" in m else "มาตัง (Matang)")
        fc_m = db.total_fixed_cost(m)
        cp_m = db.get_comm_pct(m)
        s_m = summarize(r_m, fixed_costs=fc_m, comm_pct=cp_m)

        margin_pct = (s_m.net_profit / s_m.net_sales * 100.0) if s_m.net_sales > 0 else 0.0
        rows.append({
            "ช่องทาง / ร้านค้า": f"{shop_title} ({m})",
            "ชื่อร้าน": shop_title,
            "งวด": m,
            "งวดเดือน": m,
            "จำนวนคำสั่งซื้อ": s_m.orders,
            "จำนวนชิ้น": s_m.units,
            "ยอดขายสุทธิ": s_m.net_sales,
            "เงินโอนจริง (F)": s_m.net_settlement,
            "ต้นทุนสินค้า (G)": s_m.cogs,
            "กำไรสุทธิ (H)": s_m.settlement_profit,
            "กำไรสุทธิสุดท้าย": s_m.net_profit,
            "% อัตรากำไรสุทธิ": margin_pct,
        })

    return pd.DataFrame(rows)


def require_result():
    from core.pipeline import ALL_PERIODS_KEY, recalculate_with_skus

    res = st.session_state.get("result")
    cur_period = st.session_state.get("period")

    snaps = db.list_snapshots()
    saved_months = snaps["month"].tolist() if not snaps.empty else []

    # 1. กรณีไม่มี snapshot ในฐานข้อมูลเลย
    if snaps.empty:
        # ถ้ามีผลการคำนวณสดในหน่วยความจำ (เช่น อัปโหลดใหม่สดๆ ก่อนบันทึก snapshot) ให้ใช้งานต่อได้
        if res is not None:
            res = recalculate_with_skus(res, db.get_skus())
            st.session_state["result"] = res
            return res
        for k in ("result", "period", "raw", "notes", "_cached_master_excel_bytes", "_cached_master_excel_key"):
            st.session_state.pop(k, None)
        db.set_app_state("active_period", "")
        st.info("💡 กรุณาไปที่หน้า **📤 นำเข้าข้อมูล** เพื่ออัปโหลดไฟล์ Excel ก่อน")
        st.page_link("pages/2_📤_นำเข้าข้อมูล.py", label="ไปหน้านำเข้าข้อมูล", icon="📤")
        st.stop()

    # 2. ตรวจสอบว่างวดปัจจุบันยังถูกต้องและมีอยู่จริงในฐานข้อมูลหรือไม่ (ป้องกันค้างงวดที่เพิ่งถูกลบ)
    is_stale_period = (
        cur_period is not None
        and cur_period != ALL_PERIODS_KEY
        and cur_period not in saved_months
    )
    is_invalid_all = (
        cur_period == ALL_PERIODS_KEY
        and len(saved_months) < 2
    )

    if res is None or is_stale_period or is_invalid_all:
        saved_p = db.get_app_state("active_period")
        if saved_p == ALL_PERIODS_KEY and len(saved_months) >= 2:
            target_period = ALL_PERIODS_KEY
        elif saved_p and saved_p in saved_months:
            target_period = saved_p
        elif len(saved_months) >= 2:
            target_period = ALL_PERIODS_KEY
        else:
            target_period = saved_months[0]

        loaded_res = load_period_result(target_period)
        if loaded_res is not None:
            db.set_app_state("active_period", target_period)
            st.session_state.update(result=loaded_res, period=target_period, notes=[])
            return loaded_res
        else:
            for k in ("result", "period", "raw", "notes"):
                st.session_state.pop(k, None)
            st.info("💡 กรุณาไปที่หน้า **📤 นำเข้าข้อมูล** เพื่ออัปโหลดไฟล์ Excel ก่อน")
            st.page_link("pages/2_📤_นำเข้าข้อมูล.py", label="ไปหน้านำเข้าข้อมูล", icon="📤")
            st.stop()

    # 3. ถ้านั่งดูสรุปรวมทุกงวดทั้งหมด ให้โหลดรวมใหม่อัตโนมัติเผื่อเพิ่งอัปเดต SKU หรือเพิ่ม/ลบงวด
    if cur_period == ALL_PERIODS_KEY:
        refreshed = load_period_result(ALL_PERIODS_KEY)
        if refreshed is not None:
            st.session_state["result"] = refreshed
            return refreshed

    # 4. คำนวณต้นทุนใหม่เสมอเผื่อผู้ใช้เพิ่งเพิ่ม/ลบ/แก้ไขราคาทุน SKU ในฐานข้อมูล
    res = recalculate_with_skus(res, db.get_skus())
    st.session_state["result"] = res
    return res


def baht(v: float | None) -> str:
    return "-" if v is None else f"฿{v:,.0f}"
