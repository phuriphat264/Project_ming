from core.ui import init_page

init_page("วิเคราะห์ขั้นสูง", "🎛️")

from core.reloader import ensure_fresh

ensure_fresh()

import plotly.graph_objects as go
import streamlit as st

from core.export import ORDER_COL_TH
from core.metrics import detect_anomalies, what_if
from core.ui import (
    baht,
    render_kpi_card,
    render_page_header,
    render_period_selector,
    render_section_header,
    require_login,
    require_result,
    style_plotly,
    summarize_for_period,
)

require_login(admin_only=True)
res = require_result()
period = st.session_state.get("period", "")

render_page_header("จำลองราคาและตรวจจับคำสั่งซื้อขาดทุน", period=period)
period = render_period_selector(key="adv_period_sel")
res = st.session_state.get("result") or res
base = summarize_for_period(res, period)

tab_sim, tab_anom = st.tabs(["🎛️ จำลองการปรับราคา / ต้นทุน", "🚨 ตรวจจับคำสั่งซื้อที่ขาดทุน"])

with tab_sim:
    col_ctrl, col_chart = st.columns([1.1, 1.3], gap="medium")
    with col_ctrl:
        with st.container(border=True):
            render_section_header("ลองปรับตัวเลข (%)", icon="🎚️")
            price = st.slider("ปรับราคาขาย (%)", -50, 50, 0)
            cost = st.slider("ราคาทุน SKU เปลี่ยน (%)", -50, 50, 0)
            volume = st.slider("จำนวนคำสั่งซื้อเปลี่ยน (%)", -80, 200, 0)
            ads = st.slider("ค่าโฆษณาเปลี่ยน (รวม GMV Ads) (%)", -100, 200, 0)

    r = what_if(base, price, cost, volume, ads)

    with col_chart:
        with st.container(border=True):
            render_section_header("เปรียบเทียบกำไรสุทธิ", icon="📊")
            sim_color = "#10b981" if r.net_profit >= base.net_profit else ("#f59e0b" if r.net_profit >= 0 else "#f43f5e")
            fig = go.Figure(
                go.Bar(
                    x=["กำไรปัจจุบัน", "กำไรจำลอง"],
                    y=[base.net_profit, r.net_profit],
                    marker=dict(color=["#3b82f6", sim_color], cornerradius=10),
                    text=[baht(base.net_profit), baht(r.net_profit)],
                    textposition="outside",
                    cliponaxis=False,
                    width=0.42,
                    hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
                )
            )
            fig = style_plotly(fig, height=320)
            fig.update_layout(margin=dict(t=40, b=24, l=16, r=16), yaxis_title="บาท (฿)")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    m1, m2, m3 = st.columns(3, gap="medium")
    with m1:
        render_kpi_card("รายได้ทั้งหมด (จำลอง)", baht(r.net_sales), f"เดิม {baht(base.net_sales)}", delta=baht(r.net_sales - base.net_sales), delta_positive=(r.net_sales - base.net_sales) >= 0, icon="💰")
    with m2:
        render_kpi_card("กำไรสุทธิ (จำลอง)", baht(r.net_profit), f"เดิม {baht(base.net_profit)}", delta=baht(r.profit_change), delta_positive=r.profit_change >= 0, icon="📈")
    with m3:
        bep_label = baht(r.break_even_sales) if r.break_even_sales is not None else "ไม่คุ้มทุน"
        render_kpi_card("จุดคุ้มทุน (จำลอง)", bep_label, f"เดิม {baht(base.break_even_sales)}", icon="🎯")

with tab_anom:
    a = detect_anomalies(res, 40.0, 20.0)
    neg_loss = float(a["negative_profit"]["profit"].sum()) if len(a["negative_profit"]) else 0.0

    k1, k2, k3 = st.columns(3, gap="medium")
    with k1:
        render_kpi_card("คำสั่งซื้อที่ขายขาดทุน (H < 0)", f"{len(a['negative_profit']):,} รายการ", f"ขาดทุนรวม {baht(neg_loss)}", icon="🔴")
    with k2:
        render_kpi_card("ค่าธรรมเนียมเกิน 40%", f"{len(a['high_fee']):,} รายการ", "หักค่าธรรมเนียมสูงผิดปกติ", icon="🟠")
    with k3:
        render_kpi_card("คืนเงินแต่เสียค่าธรรมเนียม/ค่าส่ง", f"{len(a['refund_with_fee']):,} รายการ", "ออเดอร์ตีกลับที่มีค่าใช้จ่าย", icon="🟡")

    with st.container(border=True):
        render_section_header("รายการคำสั่งซื้อที่ขายขาดทุน (ยอดการชำระเงินทั้งหมด F น้อยกว่า ต้นทุนรวม G)", icon="🔴")
        if a["negative_profit"].empty:
            st.success("ไม่พบคำสั่งซื้อที่ขาดทุน")
        else:
            st.dataframe(a["negative_profit"].rename(columns=ORDER_COL_TH), width="stretch", hide_index=True, height=380)
