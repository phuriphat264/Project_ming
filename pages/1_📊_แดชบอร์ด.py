from core.reloader import ensure_fresh

ensure_fresh()

import plotly.graph_objects as go
import streamlit as st

from core import db
from core.metrics import (
    by_category,
    by_sku,
    calendar_monthly_trend,
    cost_breakdown,
    daily_trend,
    summarize,
    tiktok_report_table,
)
from core.pipeline import ALL_PERIODS_KEY, filter_result_by_month, list_calendar_months
from core.ui import (
    CORPORATE_PALETTE,
    baht,
    build_saved_periods_comparison_df,
    get_period_financial_params,
    init_page,
    render_kpi_card,
    render_page_header,
    render_period_selector,
    render_section_header,
    require_login,
    require_result,
    style_plotly,
)

init_page("แดชบอร์ด", "📊")
require_login(admin_only=True)
res_full = require_result()
period = st.session_state.get("period", "")

snapshots = db.list_snapshots()
render_page_header(title="📊 เช็กกำไร / ขาดทุน ตามโครงสร้าง TikTok Shop", period=period)

# เลือกสลับเดือน หรือ สรุปรวมทุกงวดทั้งหมด + ทางลัดไปหน้าแก้ไขต้นทุน/ค่าใช้จ่าย
top_bar_1, top_bar_2 = st.columns([1.5, 1.5], gap="medium")
period = render_period_selector(container=top_bar_1, key="dash_period_sel")

# กรณีข้อมูลในมุมมองที่เลือกมีหลายเดือนปฏิทิน (เช่น สรุปรวมทุกงวด หรือไฟล์เดียวมีออเดอร์ข้ามเดือน) ให้กรองเจาะเดือนปฏิทินได้ด้วย
cal_months = list_calendar_months(res_full)
selected_cal_ym = "ทั้งหมด"
if len(cal_months) > 1:
    selected_cal_ym = top_bar_1.selectbox(
        "🗓️ กรองเจาะเฉพาะเดือนปฏิทิน (ถ้าต้องการดูแยกตามวันชำระเงินจริง):",
        ["ทั้งหมด"] + cal_months,
        index=0,
        format_func=lambda m: f"แสดงทุกเดือนรวมกัน ({len(cal_months)} เดือน)" if m == "ทั้งหมด" else f"เฉพาะเดือนปฏิทิน {m}",
    )

if selected_cal_ym != "ทั้งหมด":
    res = filter_result_by_month(res_full, selected_cal_ym)
    fixed_total = db.total_fixed_cost(selected_cal_ym)
    comm_pct = db.get_comm_pct(selected_cal_ym)
    override_comm = None
    active_label = f"{period} → เดือน {selected_cal_ym}"
else:
    res = res_full
    fixed_total, comm_pct, override_comm = get_period_financial_params(period)
    active_label = period

with top_bar_2:
    exp_label = (
        f"⚙️ รวมค่าคอมฯ & ค่าใช้จ่ายโรงงานทุกงวด ({baht(fixed_total)}) — กดดู/ปรับด่วน"
        if period == ALL_PERIODS_KEY and selected_cal_ym == "ทั้งหมด"
        else f"⚙️ ค่าคอมฯ ({comm_pct:.0f}%) & ค่าใช้จ่ายโรงงาน ({baht(fixed_total)}) — กดดู/ปรับด่วน"
    )
    with st.expander(exp_label):
        if period == ALL_PERIODS_KEY and selected_cal_ym == "ทั้งหมด":
            st.caption(f"รวมค่าใช้จ่ายโรงงานของทุกงวดที่บันทึกไว้: **{baht(fixed_total)}**")
        else:
            target_exp_m = selected_cal_ym if selected_cal_ym != "ทั้งหมด" else period
            fc_items = db.get_fixed_costs(target_exp_m)
            if not fc_items.empty:
                for _, r in fc_items.iterrows():
                    st.write(f"• {r['item']}: **฿{r['amount']:,.0f}**")
            else:
                st.caption("ไม่มีรายการค่าใช้จ่ายโรงงานเพิ่มเติมในงวดนี้ (คิดเฉพาะราคาทุนจากชีต SKU)")
        st.page_link("pages/3_📦_สินค้าและต้นทุน.py", label="ไปเพิ่ม / ลบ / แก้ไข ค่าใช้จ่ายและราคาทุน →", icon="✏️")

s = summarize(
    res,
    fixed_costs=fixed_total,
    comm_pct=comm_pct,
    override_sales_commission=override_comm,
)
sku_df = by_sku(res)
losing_sku_cnt = int((sku_df["กำไรขั้นต้น"] < 0).sum()) if not sku_df.empty else 0

# 1. แบนเนอร์ฟันธงตัวใหญ่: ขาดทุนไหมจากราคาทุน SKU!
scope_prefix = f"[{active_label}] " if active_label else ""
if s.rough_profit >= 0:
    banner_bg, banner_bd, banner_fg = "#f0fdf4", "#86efac", "#166534"
    verdict_title = f"✅ {scope_prefix}การขายไม่ขาดทุน! กำไรจากการขายสินค้า +{baht(s.rough_profit)}"
else:
    banner_bg, banner_bd, banner_fg = "#fef2f2", "#fca5a5", "#991b1b"
    verdict_title = f"🚨 {scope_prefix}การขายขาดทุน! ติดลบ {baht(s.rough_profit)} (เทียบจากราคาทุน SKU)"

sub_verdict = (
    f"พบออเดอร์ที่ขายขาดทุน <b>{s.losing_orders_count:,} ออเดอร์</b> (รวม {baht(s.losing_orders_loss)}) · "
    f"สินค้าที่ขาดทุน <b>{losing_sku_cnt:,} SKU</b>"
)
if s.gmv_ads_settlement > 0:
    sub_verdict += f" · หักโฆษณาด้วย GMV ในรายงานแล้ว <b>{baht(s.gmv_ads_settlement)}</b>"
if s.sales_commission > 0 or s.fixed_costs > 0:
    true_tag = f"กำไรสุทธิคงเหลือ +{baht(s.net_profit)}" if s.net_profit >= 0 else f"ขาดทุนสุทธิ {baht(s.net_profit)}"
    sub_verdict += f" · หักค่าคอมฯ และค่าใช้จ่ายรายเดือนตอนท้ายแล้ว: <b>{true_tag}</b>"

st.markdown(
    f'<div style="background:{banner_bg};border:2px solid {banner_bd};border-radius:14px;padding:18px 24px;margin-bottom:18px;">'
    f'<div style="font-size:1.45rem;font-weight:700;color:{banner_fg};">{verdict_title}</div>'
    f'<div style="font-size:1.05rem;color:#334155;margin-top:6px;">{sub_verdict}</div>'
    f"</div>",
    unsafe_allow_html=True,
)

# 2. การ์ดตัวเลขหลัก 4 ใบ ตรงตามคอลัมน์ F, G, H ในชีตรายละเอียดคำสั่งซื้อ + กำไรสุทธิรายเดือน
k1, k2, k3, k4 = st.columns(4)
with k1:
    settle_note = f"รายได้ทั้งหมด {baht(s.net_sales)} − ค่าธรรมเนียม {baht(s.platform_fees)}"
    if s.gmv_ads_settlement > 0:
        settle_note += f" − โฆษณา GMV {baht(s.gmv_ads_settlement)}"
    render_kpi_card(
        "1. ยอดการชำระเงินทั้งหมด (F)",
        baht(s.net_settlement),
        settle_note,
        icon="💵",
    )
with k2:
    cost_sub = f"มูลค่าต้นทุน SKU {baht(s.cogs)}"
    if s.ads > 0:
        cost_sub += f" + แอดภายนอก {baht(s.ads)}"
    elif s.total_ads > 0:
        cost_sub += f" (โฆษณา GMV {baht(s.total_ads)} หักใน F แล้ว)"
    render_kpi_card(
        "2. หัก ต้นทุนรวม (G)",
        baht(s.cogs + s.ads),
        cost_sub,
        icon="📦",
    )
with k3:
    h_sub = f"ขายสุทธิ {s.units:,.0f} ชิ้น ({s.orders:,} ออเดอร์)"
    if abs(s.order_only_profit - s.settlement_profit) >= 1:
        h_sub = f"ก่อนโฆษณา GMV: {baht(s.order_only_profit)} · {s.orders:,} ออเดอร์"
    render_kpi_card(
        "3. กำไรหลังหักโฆษณา GMV (F − G)",
        baht(s.rough_profit),
        h_sub,
        delta="ไม่ขาดทุน" if s.rough_profit >= 0 else "ขาดทุน!",
        delta_positive=s.rough_profit >= 0,
        icon="📊",
    )
with k4:
    deduct_after = s.sales_commission + s.fixed_costs
    overhead_note = (
        f"หักทีหลัง: ค่าคอม {baht(s.sales_commission)} + รายเดือน {baht(s.fixed_costs)}"
        if deduct_after > 0
        else "ยังไม่มีค่าใช้จ่ายรายเดือนเพิ่มเติม"
    )
    render_kpi_card(
        "4. กำไรสุทธิสุดท้าย (หักรายเดือน)",
        baht(s.net_profit),
        overhead_note,
        delta="กำไรสุทธิ" if s.net_profit >= 0 else "ขาดทุนสุทธิ!",
        delta_positive=s.net_profit >= 0,
        icon="🏭",
    )

PLOT_CFG = {"displayModeBar": False}

# 2.5 กราฟและตารางเปรียบเทียบผลประกอบการแยกตามแต่ละเดือน (แสดงเมื่อดูสรุปรวมทุกงวด หรือมีตั้งแต่ 2 งวดขึ้นไป)
comp_df = build_saved_periods_comparison_df() if len(snapshots) >= 1 else None
cal_comp_df = calendar_monthly_trend(res_full) if len(cal_months) >= 2 else None

if comp_df is not None and (period == ALL_PERIODS_KEY or len(comp_df) >= 2):
    with st.container(border=True):
        render_section_header("เปรียบเทียบผลประกอบการแยกตามแต่ละงวดเดือน (รายได้ · ยอดชำระ F · ต้นทุน G · กำไรสุทธิ)", icon="📆")
        fig_m = go.Figure()
        fig_m.add_bar(
            x=comp_df["งวดเดือน"],
            y=comp_df["รายได้ทั้งหมด"],
            name="รายได้ทั้งหมด",
            marker=dict(color="rgba(59, 130, 246, 0.30)", line=dict(color="#3b82f6", width=1.4), cornerradius=6),
            hovertemplate="รายได้ทั้งหมด: <b>฿%{y:,.0f}</b><extra></extra>",
        )
        fig_m.add_bar(
            x=comp_df["งวดเดือน"],
            y=comp_df["ยอดการชำระเงินทั้งหมด (F)"],
            name="ยอดชำระทั้งหมด (F)",
            marker=dict(color="#6366f1", cornerradius=6),
            hovertemplate="ยอดชำระทั้งหมด (F): <b>฿%{y:,.0f}</b><extra></extra>",
        )
        fig_m.add_bar(
            x=comp_df["งวดเดือน"],
            y=comp_df["ต้นทุนรวม (G)"],
            name="ต้นทุนรวม (G)",
            marker=dict(color="#f59e0b", cornerradius=6),
            hovertemplate="ต้นทุนรวม (G): <b>฿%{y:,.0f}</b><extra></extra>",
        )
        fig_m.add_scatter(
            x=comp_df["งวดเดือน"],
            y=comp_df["กำไรสุทธิสุดท้าย"],
            name="กำไรสุทธิสุดท้าย",
            mode="lines+markers+text",
            text=[baht(v) for v in comp_df["กำไรสุทธิสุดท้าย"]],
            textposition="top center",
            cliponaxis=False,
            line=dict(color="#059669", width=3.5),
            marker=dict(
                size=10,
                color=["#f43f5e" if v < 0 else "#10b981" for v in comp_df["กำไรสุทธิสุดท้าย"]],
                line=dict(width=2.5, color="#ffffff"),
            ),
            hovertemplate="กำไรสุทธิสุดท้าย: <b>฿%{y:,.0f}</b><extra></extra>",
        )
        fig_m = style_plotly(fig_m, height=360)
        fig_m.update_layout(
            barmode="group",
            hovermode="x unified",
            yaxis_title="บาท (฿)",
            xaxis_title="งวดเดือน",
            margin=dict(t=42, b=24, l=16, r=16),
        )
        fig_m.update_xaxes(type="category")
        st.plotly_chart(fig_m, width="stretch", config=PLOT_CFG)
        st.dataframe(comp_df, width="stretch", hide_index=True)
elif cal_comp_df is not None and not cal_comp_df.empty:
    with st.container(border=True):
        render_section_header("สรุปแยกตามเดือนปฏิทินในไฟล์นี้", icon="🗓️")
        st.dataframe(cal_comp_df, width="stretch", hide_index=True)

# 3. ตารางเช็กสินค้าแต่ละตัว (ตรงตามคอลัมน์ ราคาต่อหน่วย I และ มูลค่า J ของชีต Order)
with st.container(border=True):
    top_l, top_r = st.columns([2.5, 1])
    with top_l:
        render_section_header("เช็กรายสินค้า (SKU): ราคาต่อหน่วย (I) · มูลค่าต้นทุน (J) · กำไร/ขาดทุน", icon="🔍")
    with top_r:
        only_loss = st.checkbox(f"🔴 ดูเฉพาะสินค้าที่ขาดทุน ({losing_sku_cnt} รายการ)", value=False)

    if sku_df.empty:
        st.caption("ไม่มีข้อมูลรายสินค้า")
    else:
        view_sku = sku_df[sku_df["กำไรขั้นต้น"] < 0] if only_loss else sku_df
        show_cols = [
            "สถานะ",
            "SKU",
            "ชื่อสินค้า",
            "จำนวนขาย",
            "ราคาทุน/หน่วย",
            "ยอดขายหลังส่วนลด",
            "ยอดการชำระเงินทั้งหมด",
            "มูลค่าต้นทุน",
            "กำไรขั้นต้น",
        ]
        st.dataframe(
            view_sku[show_cols].rename(columns={"กำไรขั้นต้น": "กำไร / ขาดทุน"}),
            width="stretch",
            hide_index=True,
            height=340,
        )

# 4. กราฟน้ำตก (Waterfall): เส้นทางเงินตามโครงสร้างรายงาน TikTok Shop
with st.container(border=True):
    render_section_header("เส้นทางของเงิน: รายได้ทั้งหมด → ยอดการชำระเงินทั้งหมด (F) → หักต้นทุน (G) → กำไรสุทธิ", icon="🌊")
    wf_x = ["รายได้ทั้งหมด", "ค่าธรรมเนียมทั้งหมด"]
    wf_y = [s.net_sales, -s.platform_fees]
    wf_measure = ["absolute", "relative"]
    wf_text = [baht(s.net_sales), f"-{baht(s.platform_fees)}"]

    net_adj_gmv = -s.gmv_ads_settlement + s.other_adjustment
    if abs(net_adj_gmv) >= 1:
        adj_lbl = "โฆษณา GMV / ปรับยอด" if s.gmv_ads_settlement > 0 else "การปรับยอด"
        wf_x.append(adj_lbl)
        wf_y.append(net_adj_gmv)
        wf_measure.append("relative")
        wf_text.append(baht(net_adj_gmv))

    wf_x += ["ยอดชำระทั้งหมด (F)", "ต้นทุน SKU (G)"]
    wf_y += [0, -s.cogs]
    wf_measure += ["total", "relative"]
    wf_text += [baht(s.net_settlement), f"-{baht(s.cogs)}"]

    if s.ads > 0:
        wf_x.append("ค่าแอดภายนอก")
        wf_y.append(-s.ads)
        wf_measure.append("relative")
        wf_text.append(f"-{baht(s.ads)}")

    if s.sales_commission > 0 or s.fixed_costs > 0:
        wf_x += ["กำไรจากการขาย (H)", "ค่าคอมฯ & รายเดือน", "กำไรสุทธิสุดท้าย"]
        wf_y += [0, -(s.sales_commission + s.fixed_costs), 0]
        wf_measure += ["total", "relative", "total"]
        wf_text += [baht(s.rough_profit), f"-{baht(s.sales_commission + s.fixed_costs)}", baht(s.net_profit)]
    else:
        wf_x += ["กำไรสุทธิ (H)"]
        wf_y += [0]
        wf_measure += ["total"]
        wf_text += [baht(s.net_profit)]

    fig_wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=wf_measure,
            x=wf_x,
            y=wf_y,
            text=wf_text,
            textposition="outside",
            cliponaxis=False,
            connector=dict(line=dict(color="#cbd5e1", width=1.5, dash="dot")),
            increasing=dict(marker=dict(color="#10b981")),
            decreasing=dict(marker=dict(color="#f43f5e")),
            totals=dict(marker=dict(color="#3b82f6" if s.net_profit >= 0 else "#ef4444")),
            hovertemplate="<b>%{x}</b><br>จำนวนเงิน: %{text}<extra></extra>",
        )
    )
    fig_wf = style_plotly(fig_wf, height=360)
    fig_wf.update_layout(margin=dict(t=42, b=24, l=16, r=16), yaxis_title="บาท (฿)")
    st.plotly_chart(fig_wf, width="stretch", config=PLOT_CFG)

# 5. กราฟ 2 คอลัมน์: Donut สัดส่วนค่าใช้จ่ายตามหมวดจริงของ TikTok & แท่งกำไรตามหมวดหมู่
left, right = st.columns(2, gap="medium")
with left:
    with st.container(border=True):
        render_section_header("สัดส่วนต้นทุน ค่าธรรมเนียม และค่าโฆษณาทั้งหมด", icon="🍩")
        cb = cost_breakdown(res, s.ads, sales_commission=s.sales_commission, fixed_costs=s.fixed_costs)
        if cb.empty:
            st.caption("ไม่มีข้อมูลต้นทุน")
        else:
            total_cost_all = float(cb["จำนวนเงิน"].sum())
            fig_pie = go.Figure(
                go.Pie(
                    labels=cb["รายการ"],
                    values=cb["จำนวนเงิน"],
                    hole=0.64,
                    sort=True,
                    direction="clockwise",
                    marker=dict(colors=CORPORATE_PALETTE, line=dict(color="#ffffff", width=3)),
                    textinfo="percent",
                    textposition="inside",
                    insidetextorientation="horizontal",
                    textfont=dict(size=13, color="#ffffff"),
                    hovertemplate="<b>%{label}</b><br>฿%{value:,.0f} (%{percent})<extra></extra>",
                )
            )
            fig_pie = style_plotly(fig_pie, height=370)
            fig_pie.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=13),
                ),
                margin=dict(t=16, b=16, l=8, r=150),
                annotations=[
                    dict(
                        text=f"<span style='font-size:13px;color:#64748b;'>รวมรายจ่าย</span><br><b>{baht(total_cost_all)}</b>",
                        x=0.5,
                        y=0.5,
                        font=dict(size=18, color="#0f172a"),
                        showarrow=False,
                    )
                ],
            )
            st.plotly_chart(fig_pie, width="stretch", config=PLOT_CFG)

with right:
    with st.container(border=True):
        render_section_header("กำไร / ขาดทุน แยกตามหมวดหมู่สินค้า", icon="📊")
        cat = by_category(res)
        bar_colors = ["#f43f5e" if v < 0 else "#10b981" for v in cat["กำไร"]]
        fig_cat = go.Figure(
            go.Bar(
                x=cat["กำไร"],
                y=cat["หมวดหมู่"],
                orientation="h",
                marker=dict(color=bar_colors, cornerradius=8),
                text=[f"+{baht(v)}" if v > 0 else baht(v) for v in cat["กำไร"]],
                textposition="outside",
                cliponaxis=False,
                width=0.55,
                hovertemplate="<b>%{y}</b><br>กำไร/ขาดทุน: ฿%{x:,.0f}<extra></extra>",
            )
        )
        fig_cat = style_plotly(fig_cat, height=370)
        min_x = float(cat["กำไร"].min()) if not cat.empty else 0.0
        max_x = float(cat["กำไร"].max()) if not cat.empty else 100.0
        pad = max(abs(min_x), abs(max_x), 100.0) * 0.28
        fig_cat.update_layout(
            yaxis=dict(autorange="reversed", title="", showgrid=False),
            xaxis=dict(
                title="กำไร / ขาดทุน (บาท)",
                showgrid=True,
                gridcolor="#e2e8f0",
                griddash="dot",
                zeroline=True,
                zerolinecolor="#94a3b8",
                zerolinewidth=2,
                range=[min(0.0, min_x - pad), max(0.0, max_x + pad)],
            ),
            margin=dict(t=20, b=24, l=12, r=40),
        )
        st.plotly_chart(fig_cat, width="stretch", config=PLOT_CFG)

# 6. กราฟแนวโน้มรายวัน
with st.container(border=True):
    col_t_head, col_t_mode = st.columns([2.2, 1.2], gap="medium")
    with col_t_head:
        render_section_header("แนวโน้มรายได้และกำไรตามวัน (Daily Trend)", icon="📅")
    with col_t_mode:
        trend_view_mode = st.radio(
            "มุมมองกำไร:",
            ["กำไรคำนวณสุทธิ (H = F − G)", "กำไรเฉพาะคำสั่งซื้อ (ก่อนหักแอด GMV)"],
            horizontal=True,
            label_visibility="collapsed",
        )

    trend = daily_trend(res)
    if trend.empty:
        st.caption("ไม่มีข้อมูลวันที่")
    else:
        use_order_profit = trend_view_mode.startswith("กำไรเฉพาะคำสั่งซื้อ")
        profit_col = "กำไรเฉพาะคำสั่งซื้อ" if use_order_profit else "กำไร"
        profit_legend = "กำไรคำสั่งซื้อ (ก่อนแอด GMV)" if use_order_profit else "กำไรสุทธิ (H = F − G)"

        fig_tr = go.Figure()
        fig_tr.add_bar(
            x=trend["วันที่"],
            y=trend["รายได้ทั้งหมด"],
            name="รายได้ทั้งหมด",
            marker=dict(color="rgba(59, 130, 246, 0.25)", line=dict(color="#3b82f6", width=1.2), cornerradius=6),
            hovertemplate="รายได้ทั้งหมด: <b>฿%{y:,.0f}</b><extra></extra>",
        )
        if not use_order_profit and float(trend["โฆษณา GMV"].sum()) > 0:
            fig_tr.add_bar(
                x=trend["วันที่"],
                y=trend["โฆษณา GMV"],
                name="หักค่าแอด GMV",
                marker=dict(color="rgba(239, 68, 68, 0.40)", line=dict(color="#ef4444", width=1.0), cornerradius=4),
                hovertemplate="หักแอด GMV: <b>฿%{y:,.0f}</b><extra></extra>",
            )

        fig_tr.add_scatter(
            x=trend["วันที่"],
            y=trend[profit_col],
            name=profit_legend,
            mode="lines+markers",
            line=dict(color="#059669", width=3.2, shape="spline", smoothing=0.75),
            marker=dict(
                size=9,
                color=["#f43f5e" if v < 0 else "#10b981" for v in trend[profit_col]],
                line=dict(width=2.5, color="#ffffff"),
            ),
            hovertemplate=f"{profit_legend}: <b>฿%{{y:,.0f}}</b><extra></extra>",
        )
        fig_tr = style_plotly(fig_tr, height=360)
        fig_tr.update_layout(hovermode="x unified", yaxis_title="บาท (฿)")
        st.plotly_chart(fig_tr, width="stretch", config=PLOT_CFG)
        st.caption(
            "💡 หมายเหตุ: กำไรสุทธิของบางวันอาจติดลบเนื่องจากระบบตัดรอบหักค่าโฆษณา GMV ของ TikTok เป็นก้อนในวันนั้น "
            "(สามารถสลับปุ่มด้านบนเป็น 'กำไรเฉพาะคำสั่งซื้อ' เพื่อดูกำไรจากการขายสินค้าล้วนๆ โดยไม่รวมก้อนค่าแอด GMV ได้)"
        )

# 7. ตารางรายละเอียดตามโครงสร้างชีต 'รายงาน' และ 'คำอธิบายค่าธรรมเนียม' ของ TikTok Shop
with st.expander("📋 เปิดดูรายละเอียดทุกคอลัมน์ตามโครงสร้างชีต 'รายงาน' ของ TikTok Shop", expanded=False):
    st.dataframe(tiktok_report_table(res), width="stretch", hide_index=True, height=460)
