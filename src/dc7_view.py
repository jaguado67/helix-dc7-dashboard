from __future__ import annotations

import base64
import html
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import APP_SUBTITLE, APP_TITLE, BRAND_NAME, LOGOS_DIR, VERSION
from src.dc7_model import DC7Model

NAVY="#0b2748"; NAVY2="#0d3b73"; TEXT="#0b2038"; MUTED="#687b8f"; BORDER="#d5e0ea"; GRID="#e8eef4"
GREEN="#14936f"; RED="#d83a3a"; BLUE="#2f80ed"; EARLY="#18845f"; BASELINE="#aab8c8"

CSS=f"""
<style>
#MainMenu{{visibility:hidden}} footer{{visibility:hidden}} header[data-testid="stHeader"]{{background:transparent;height:0;min-height:0}}
[data-testid="stToolbar"]{{display:none!important}} [data-testid="stSidebar"]{{display:none!important}} [data-testid="collapsedControl"]{{display:none!important}}
.block-container{{padding-top:.35rem;padding-bottom:2rem;max-width:1680px}} [data-testid="stAppViewContainer"]{{background:#fff}}
html,body,[class*="css"]{{font-family:Arial,Helvetica,sans-serif;color:{TEXT}}} [data-testid="stVerticalBlock"]{{gap:.55rem}}
.helix-header{{background:{NAVY};color:#fff;min-height:84px;padding:11px 17px;display:grid;grid-template-columns:105px minmax(500px,1.65fr) 250px 295px 112px;align-items:center;column-gap:16px}}
.logo-card{{background:#fff;border-radius:5px;height:55px;padding:4px 8px;display:flex;align-items:center;justify-content:center}} .logo-card img{{max-width:100%;max-height:47px;object-fit:contain}}
.brand-title{{font-size:26px;font-weight:850;line-height:1.02;white-space:nowrap}} .brand-subtitle{{font-size:13px;font-weight:650;margin-top:7px;color:#d7e2ed}}
.header-center{{display:flex;justify-content:center;gap:8px;align-items:center;white-space:nowrap}} .header-chip{{border:1px solid #6f87a2;border-radius:6px;padding:9px 14px;font-size:12px;font-weight:850}}
.header-meta{{text-align:right;white-space:nowrap;line-height:1.35}} .header-meta .line{{font-size:12px;font-weight:800;margin:2px 0}} .header-meta .value{{font-size:13px;font-weight:900}}
.project-strip{{margin-top:14px;background:{NAVY};color:#fff;padding:11px 15px;border-radius:3px;display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:850}} .project-strip .right{{font-weight:600;color:#dce6f0}}
.section-caption{{font-size:17px;font-weight:900;color:#000;margin:16px 0 3px 12px}} .panel{{background:#fff;border:1px solid {BORDER};border-radius:5px;padding:10px 12px 12px}}
.panel.schedule{{background:#f5fbf8;border-top:4px solid {GREEN}}} .panel-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:12px}} .panel-title{{font-size:17px;font-weight:900;color:{NAVY}}} .panel-note{{font-size:12px;color:{MUTED};text-align:right}}
.time-pill{{display:inline-block;background:{GREEN};color:#fff;border-radius:14px;padding:6px 14px;font-size:12px;font-weight:900;margin-right:9px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(8,minmax(120px,1fr));gap:10px}} .kpi{{background:#fff;border:1px solid #b7dfd2;border-radius:8px;padding:13px 10px;min-height:108px;text-align:center}}
.kpi .label{{font-size:12px;color:#495e72;font-weight:700}} .kpi .value{{font-size:22px;color:#071a30;font-weight:900;margin-top:11px}} .kpi .sub{{font-size:12px;color:{MUTED};margin-top:6px;line-height:1.35}}
.good{{color:{EARLY}!important}} .bad{{color:{RED}!important}} .neutral{{color:{BLUE}!important}}
.activity-wrap{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:7px}} .activity-card{{background:#f8fafc;border:1px solid {BORDER};border-radius:7px;padding:12px;text-align:center}} .activity-card .num{{font-size:26px;font-weight:900;color:{NAVY}}} .activity-card .lab{{font-size:12px;color:{MUTED};margin-top:3px}}
.stats-table,.detail-table{{width:100%;border-collapse:collapse;font-size:13px}} .stats-table th,.detail-table th{{background:#0c478d;color:#fff;padding:9px 7px;border:1px solid #23446c;font-weight:800;text-align:center}} .stats-table td,.detail-table td{{padding:8px 7px;border:1px solid #ccd7e1;text-align:center}} .stats-table td:first-child,.detail-table td:first-child{{font-weight:800;text-align:left;background:#f7f9fc}}
.gate-wrap{{background:#10151d;border-radius:8px;padding:12px;margin-top:4px;max-height:440px;overflow:auto;border:1px solid #2b3542}} .gate-table{{width:100%;border-collapse:collapse;font-size:12px;color:#eef3f7;min-width:1140px}} .gate-table th{{position:sticky;top:0;background:#252b35;color:#cfd7e1;text-align:left;padding:10px 10px;border-right:1px solid #37404c;border-bottom:1px solid #414a56;font-weight:600;z-index:1}} .gate-table td{{padding:9px 10px;border-right:1px solid #26303b;border-bottom:1px solid #252f39;white-space:nowrap}}
.var-late,.tf-neg{{color:#ff8f8f;font-weight:800}} .var-early,.tf-pos{{color:#7ad6ae;font-weight:800}} .var-zero{{color:#dfe7ef;font-weight:700}} .tf-zero{{color:#f0c96d;font-weight:800}}
.scope-note{{font-size:12px;color:{MUTED};padding:4px 2px 0}}
[data-baseweb="select"]>div{{font-size:14px!important;min-height:46px}} [data-testid="stSelectbox"] label{{font-size:14px!important;font-weight:700!important}}
.gate-legend{{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:4px 0 8px 2px;font-size:13px;color:{MUTED}}}
.gate-legend .item{{display:flex;align-items:center;gap:6px}} .gate-legend .diamond{{width:10px;height:10px;background:#7048c7;transform:rotate(45deg);display:inline-block}} .gate-legend .dot{{width:10px;height:10px;border-radius:50%;background:{BLUE};display:inline-block}} .gate-legend .line-late{{width:24px;height:4px;background:{RED};display:inline-block;border-radius:4px}} .gate-legend .line-early{{width:24px;height:4px;background:{EARLY};display:inline-block;border-radius:4px}} .gate-legend .line-zero{{width:24px;height:4px;background:{BLUE};display:inline-block;border-radius:4px}}
.small-note{{font-size:12px;color:{MUTED};margin:0 0 8px 2px;line-height:1.35}}
@media(max-width:1450px){{.kpi-grid{{grid-template-columns:repeat(4,1fr)}}}}
@media(max-width:1200px){{.helix-header{{grid-template-columns:90px minmax(360px,1fr) 210px 260px 92px;column-gap:10px}}.brand-title{{font-size:20px}}.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}
</style>
"""

def _safe(x): return html.escape(str(x))
def _fmt_date(x): return "—" if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%d-%b-%Y")
def _fmt_days(x): return "—" if x is None or pd.isna(x) else f"{int(round(float(x))):+d} days"
def _fmt_days_abs(x): return "—" if x is None or pd.isna(x) else f"{abs(int(round(float(x))))} days"
def _fmt_pct(x): return "—" if x is None or pd.isna(x) else f"{float(x):.1f}%"
def _var_class(x): return "" if x is None or pd.isna(x) else ("good" if x > 0 else ("bad" if x < 0 else "neutral"))
def _timeline_color(x): return EARLY if pd.notna(x) and x > 0 else (RED if pd.notna(x) and x < 0 else BLUE)

def _logo(keyword):
    roots=[LOGOS_DIR, Path(__file__).resolve().parents[1]/"LOGOS"]
    for root in roots:
        if root.exists():
            m=sorted([p for p in root.iterdir() if p.is_file() and keyword.lower() in p.name.lower()])
            if m:
                return base64.b64encode(m[0].read_bytes()).decode("ascii")
    return ""


def _layout(height=360,left=55,bottom=50,top=48):
    return dict(
        height=height,
        margin=dict(l=left,r=35,t=top,b=bottom),
        paper_bgcolor="#fff", plot_bgcolor="#fff",
        font=dict(family="Arial", size=13, color=TEXT),
        hoverlabel=dict(bgcolor="#fff", font_size=13),
        legend=dict(orientation="h", y=1.13, x=0, font=dict(size=13)),
        title_font=dict(size=16, color=TEXT),
        xaxis=dict(tickfont=dict(size=12), title_font=dict(size=14)),
        yaxis=dict(tickfont=dict(size=12), title_font=dict(size=14)),
    )


def render_header(m: DC7Model):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="helix-header">
      <div class="logo-card"><img src="data:image/png;base64,{_logo('toro')}"></div>
      <div><div class="brand-title">{BRAND_NAME} {APP_TITLE}</div><div class="brand-subtitle">{APP_SUBTITLE}</div></div>
      <div class="header-center"><span class="header-chip">DC7 PROJECT DETAIL</span><span class="header-chip">v{VERSION}</span></div>
      <div class="header-meta">
        <div class="line">Latest Data Date&nbsp;&nbsp;<span class="value">{_fmt_date(m.data_date)}</span></div>
        <div class="line">Current Update&nbsp;&nbsp;<span class="value">{_safe(m.update_path.stem)}</span></div>
        <div class="line">Scope&nbsp;&nbsp;<span class="value">HELIX Electric</span></div>
      </div>
      <div class="logo-card"><img src="data:image/png;base64,{_logo('helix')}"></div>
    </div>
    <div class="project-strip"><span>DC7 VIEW</span><span class="right">Full-project finish · HELIX Activity Code scope analytics</span></div>
    """, unsafe_allow_html=True)


def render_kpis(m: DC7Model):
    fv = m.finish_variance_days
    counts = m.status_counts()
    p = m.status_percentages()
    st.markdown('<div class="section-caption">PROJECT STATUS SUMMARY</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel schedule"><div class="panel-head"><div><span class="time-pill">TIME</span><span class="panel-title">SCHEDULE PERFORMANCE</span></div><div class="panel-note">Project finish from DC7 main project · HELIX scope activity mix</div></div>', unsafe_allow_html=True)
    cards = [
        ("Baseline Completion", _fmt_date(m.baseline_finish), m.baseline_path.stem, ""),
        ("Current Forecast Finish", _fmt_date(m.current_finish), _fmt_days(fv) + " vs Baseline", _var_class(fv)),
        ("Finish Variance", _fmt_days(fv), "Baseline − Current", _var_class(fv)),
        ("Completed Activities", _fmt_pct(p["Completed %"]), f"{counts['Completed']:,} of {counts['Total']:,}", "good" if p["Completed %"] > 0 else ""),
        ("In Progress Activities", _fmt_pct(p["In Progress %"]), f"{counts['In Progress']:,} of {counts['Total']:,}", "neutral" if p["In Progress %"] > 0 else ""),
        ("Not Started Activities", _fmt_pct(p["Not Started %"]), f"{counts['Not Started']:,} of {counts['Total']:,}", "bad" if p["Not Started %"] > 0 else ""),
        ("HELIX Scope Activities", f"{counts['Total']:,}", f"{counts['Completed']} C · {counts['In Progress']} IP · {counts['Not Started']} NS", ""),
        ("Current Data Date", _fmt_date(m.data_date), "P6 last recalculation / Data Date", ""),
    ]
    h = '<div class="kpi-grid">'
    for a, b, c, d in cards:
        h += f'<div class="kpi"><div class="label">{_safe(a)}</div><div class="value {d}">{_safe(b)}</div><div class="sub">{_safe(c)}</div></div>'
    st.markdown(h + '</div></div>', unsafe_allow_html=True)


def render_scurve_and_status(m: DC7Model):
    st.markdown('<div class="section-caption">ACTIVITY PERFORMANCE</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.7, 0.8], gap="large")
    with c1:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">ACTIVITY S-CURVE · HELIX SCOPE</div><div class="panel-note">Cumulative activity count · baseline / current forecast / actual completions</div></div>', unsafe_allow_html=True)
        df = m.scurve()
        if df.empty:
            st.info("Activity S-curve could not be constructed from the XER finish dates.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.Date, y=df["Baseline Planned Activities"], name="Baseline Planned Activities", mode="lines", line=dict(color="#446a9e", width=3), hovertemplate="<b>Baseline Planned Activities</b><br>%{x|%d-%b-%Y}<br>%{y:,.0f} activities<extra></extra>"))
            fig.add_trace(go.Scatter(x=df.Date, y=df["Current Forecast Activities"], name="Current Forecast Activities", mode="lines", line=dict(color="#d36b32", width=3), hovertemplate="<b>Current Forecast Activities</b><br>%{x|%d-%b-%Y}<br>%{y:,.0f} activities<extra></extra>"))
            fig.add_trace(go.Scatter(x=df.Date, y=df["Actual Completed Activities"], name="Actual Completed Activities", mode="lines+markers", line=dict(color=GREEN, width=3), marker=dict(size=7), connectgaps=False, hovertemplate="<b>Actual Completed Activities</b><br>%{x|%d-%b-%Y}<br>%{y:,.0f} completed<extra></extra>"))
            if pd.notna(m.data_date):
                fig.add_vline(x=m.data_date, line_dash="dash", line_color="#6d7f92", annotation_text=f"Data Date · {_fmt_date(m.data_date)}", annotation_position="top right")
            total = m.status_counts()["Total"]
            fig.update_layout(**_layout(410, 70, 55, 34), yaxis_title="Cumulative Activities", xaxis_title="Date", title=dict(text=""), legend_title_text="")
            fig.update_yaxes(range=[0, max(1, total * 1.04)], tickformat=",d", gridcolor=GRID)
            fig.update_xaxes(type="date", dtick="M3", tickformat="%b\n%Y", gridcolor=GRID)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        counts = m.status_counts(); ratio = m.activity_completion_ratio
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">OVERALL ACTIVITY STATUS</div></div>', unsafe_allow_html=True)
        h = '<div class="activity-wrap">'
        for lab, val in [("Total", counts['Total']), ("Completed", counts['Completed']), ("In Progress", counts['In Progress']), ("Not Started", counts['Not Started'])]:
            h += f'<div class="activity-card"><div class="num">{val:,}</div><div class="lab">{lab}</div></div>'
        p = m.status_percentages()
        h += f'</div><div class="scope-note">Completed: <b>{p["Completed %"]:.1f}%</b><br>In Progress: <b>{p["In Progress %"]:.1f}%</b><br>Not Started: <b>{p["Not Started %"]:.1f}%</b><br>Open HELIX Activities: <b>{counts["In Progress"] + counts["Not Started"]:,}</b></div></div>'
        st.markdown(h, unsafe_allow_html=True)


def render_windows(m: DC7Model):
    st.markdown('<div class="section-caption">AREA START–FINISH COMPARISON · BASELINE VS CURRENT</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-note">Gray = Baseline representative Start → Baseline Finish. Color = Current/Actual representative Start → Current Forecast Finish. The Start uses the same meaningful production anchor activity in Baseline and Current, avoiding isolated early underground/underslab work. Red = later finish, green = earlier finish, blue = no finish-date change.</div>', unsafe_allow_html=True)
    df = m.area_windows()
    if df.empty:
        st.info("No QTS - AREA assignments found for HELIX scope.")
        return
    fig = go.Figure(); dates = []
    for i, r in df.iterrows():
        base_y = 2 * (len(df) - 1 - i) + .25
        cur_y = base_y - .5
        bs, bf, cs, cf = r["Baseline Start"], r["Baseline Finish"], r["Current Start"], r["Current Forecast Finish"]
        dates += [x for x in [bs, bf, cs, cf] if pd.notna(x)]
        if pd.notna(bs) and pd.notna(bf):
            fig.add_trace(go.Scatter(x=[bs, bf], y=[base_y, base_y], mode="lines+markers", line=dict(color=BASELINE, width=8), marker=dict(size=8, color=BASELINE), showlegend=False, hovertemplate=f"<b>{r.Area} · Baseline</b><br>Start: {_fmt_date(bs)}<br>Finish: {_fmt_date(bf)}<extra></extra>"))
        if pd.notna(cs) and pd.notna(cf):
            v = r["Finish Variance (d)"]; col = _timeline_color(v)
            fig.add_trace(go.Scatter(x=[cs, cf], y=[cur_y, cur_y], mode="lines+markers", line=dict(color=col, width=9), marker=dict(size=9, color=col), showlegend=False, hovertemplate=f"<b>{r.Area} · Current</b><br>Representative Start: {_fmt_date(cs)}<br>Start Anchor: {_safe(r['Start Anchor ID'])}<br>Finish: {_fmt_date(cf)}<br>Start Variance: {_fmt_days(r['Start Variance (d)'])}<br>Finish Variance: {_fmt_days(v)}<br>Activity Completion: {r['Activity Completion %']:.1f}%<extra></extra>"))
            fig.add_annotation(x=cf, y=cur_y, text=f"{_fmt_days(v)} · {r['Activity Completion %']:.1f}%", showarrow=False, xanchor="left", xshift=8, font=dict(size=12, color=col))
    if dates:
        lo = min(dates) - pd.Timedelta(days=25); hi = max(dates) + pd.Timedelta(days=45)
        fig.update_xaxes(type="date", range=[lo, hi], dtick="M2", tickformat="%b\n%Y", gridcolor=GRID, title="Date")
    if pd.notna(m.data_date):
        fig.add_vline(x=m.data_date, line_dash="dash", line_color="#62788e", annotation_text=f"Data Date · {_fmt_date(m.data_date)}", annotation_position="top right")
    tickvals = []; ticktext = []
    for i, r in df.iterrows():
        b = 2 * (len(df) - 1 - i) + .25
        tickvals.append(b - .25); ticktext.append(r.Area)
    fig.update_yaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext, gridcolor="#fff", zeroline=False, tickfont=dict(size=13))
    fig.update_layout(**_layout(max(460, 68 * len(df) + 100), 100, 55, 28), showlegend=False, title=dict(text=""))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_fte_ready(m: DC7Model):
    st.markdown('<div class="section-caption">FTE READY MILESTONES · BASELINE VS CURRENT</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-note">Main DC7 project only. Gray diamond = Baseline FTE Ready. Colored circle = Current FTE Ready. Variance = Baseline − Current. Green/positive = ahead, red/negative = late, blue/zero = no date change. No external-project milestones or external relationships are used.</div>', unsafe_allow_html=True)
    df = m.fte_ready_comparison()
    if df.empty:
        st.info("No comparable FTE Ready milestones were identified in the DC7 main project.")
        return

    fig = go.Figure()
    yvals = list(range(len(df) - 1, -1, -1))
    dates = []
    for y, (_, r) in zip(yvals, df.iterrows()):
        bd, cd = r["Baseline Date"], r["Current Date"]
        v = r["Finish Variance (d)"]
        dates += [x for x in [bd, cd] if pd.notna(x)]
        col = _timeline_color(v)

        if pd.notna(bd) and pd.notna(cd):
            fig.add_trace(go.Scatter(
                x=[bd, cd], y=[y, y], mode="lines",
                line=dict(color=col, width=7), showlegend=False, hoverinfo="skip"
            ))
        if pd.notna(bd):
            fig.add_trace(go.Scatter(
                x=[bd], y=[y], mode="markers",
                marker=dict(size=12, color=BASELINE, symbol="diamond"), showlegend=False,
                hovertemplate=f"<b>{r['Area']} · Baseline FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(bd)}<extra></extra>"
            ))
        if pd.notna(cd):
            fig.add_trace(go.Scatter(
                x=[cd], y=[y], mode="markers",
                marker=dict(size=12, color=col, symbol="circle"), showlegend=False,
                hovertemplate=f"<b>{r['Area']} · Current FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(cd)}<br>Finish Variance: {_fmt_days(v)}<br>Status: {_safe(r['Status'])}<extra></extra>"
            ))
            fig.add_annotation(
                x=cd, y=y, text=_fmt_days(v), showarrow=False,
                xanchor="left", xshift=9, yshift=10,
                font=dict(size=12, color=col)
            )

    if dates:
        fig.update_xaxes(
            type="date",
            range=[min(dates) - pd.Timedelta(days=20), max(dates) + pd.Timedelta(days=35)],
            dtick="M1", tickformat="%b\n%Y", gridcolor=GRID, title="Milestone Date"
        )
    if pd.notna(m.data_date):
        fig.add_vline(
            x=m.data_date, line_dash="dash", line_color="#62788e",
            annotation_text=f"Data Date · {_fmt_date(m.data_date)}", annotation_position="top right"
        )

    fig.update_yaxes(
        tickmode="array", tickvals=yvals, ticktext=df["Area"].tolist(),
        gridcolor=GRID, zeroline=False, tickfont=dict(size=13)
    )
    fig.update_layout(
        **_layout(max(350, 58 * len(df) + 110), 100, 55, 28),
        showlegend=False, title=dict(text="")
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Small audit table so every milestone shown can be found directly in the main P6 project.
    audit = df[["Area", "Activity ID", "Baseline Date", "Current Date", "Finish Variance (d)", "Status"]].copy()
    audit["Baseline Date"] = audit["Baseline Date"].apply(_fmt_date)
    audit["Current Date"] = audit["Current Date"].apply(_fmt_date)
    audit["Finish Variance"] = audit["Finish Variance (d)"].apply(_fmt_days)
    audit = audit.drop(columns=["Finish Variance (d)"])
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.caption("Source: DC7 main project only. FTE Ready is matched by the IST.6100 activity family in Baseline and Current. External projects and cross-project relationships are excluded from this dashboard.")


def render_stats(m: DC7Model):
    st.markdown('<div class="section-caption">PROJECT STATS · HELIX SCOPE</div>', unsafe_allow_html=True)
    df = m.area_stats().copy()
    h = '<div class="panel"><table class="stats-table"><thead><tr><th>Area</th><th>Total Tasks</th><th>Activity Completion %</th><th>Completed</th><th>In Progress</th><th>Not Started</th></tr></thead><tbody>'
    for _, r in df.iterrows():
        h += f'<tr><td>{r.Area}</td><td>{int(r["Total Tasks"]):,}</td><td>{r["Activity Completion %"]:.1f}%</td><td>{int(r.Completed)}</td><td>{int(r["In Progress"])} </td><td>{int(r["Not Started"])} </td></tr>'
    st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    fig = go.Figure(go.Bar(x=df["Activity Completion %"], y=df.Area, orientation="h", text=[f"{x:.1f}%" for x in df["Activity Completion %"]], textposition="outside", textfont=dict(size=13, color=TEXT), marker=dict(color="#1f6d8a")))
    fig.update_layout(**_layout(max(300, 42 * len(df) + 90), 90, 40, 28), showlegend=False, xaxis_title="Activity Completion %", yaxis_title="", title=dict(text=""))
    fig.update_xaxes(range=[0, max(10, float(df["Activity Completion %"].max()) * 1.35 + 1)], ticksuffix="%", gridcolor=GRID)
    fig.update_yaxes(autorange="reversed", gridcolor="#fff")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_progress_detail(m: DC7Model):
    st.markdown('<div class="section-caption">PROJECT PROGRESS DETAIL</div>', unsafe_allow_html=True)
    area = st.selectbox("Area / Data Hall", m.areas(), index=0, key="dc7_area")
    df = m.subarea_stats(area)
    c1, c2 = st.columns([1.15, 1], gap="large")
    with c1:
        h = f'<div class="panel"><div class="panel-head"><div class="panel-title">{area} · SUMMARY BY QTS - DASH</div></div><table class="detail-table"><thead><tr><th>Area</th><th>Tasks</th><th>Activity Completion %</th><th>Not Started</th><th>In Progress</th><th>Completed</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            label = _safe(r.Area)
            if str(r.Area) == "Electrical Infrastructure & Equipment":
                label = '<span style="color:#b36b00;font-weight:800">Electrical Infrastructure &amp; Equipment</span>'
            h += f'<tr><td>{label}</td><td>{int(r.Tasks)}</td><td>{r["Activity Completion %"]:.1f}%</td><td>{int(r["Not Started"])} </td><td>{int(r["In Progress"])} </td><td>{int(r.Completed)}</td></tr>'
        st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    with c2:
        colors = ["#c48a23" if str(x) == "Electrical Infrastructure & Equipment" else "#1f6d8a" for x in df.Area]
        fig = go.Figure(go.Bar(x=df.Area, y=df["Activity Completion %"], text=[f"{x:.1f}%" for x in df["Activity Completion %"]], textposition="outside", textfont=dict(size=13, color=TEXT), marker=dict(color=colors)))
        ymax = max(10, float(df["Activity Completion %"].max()) * 1.35 + 1) if not df.empty else 10
        fig.update_layout(**_layout(410, 70, 115, 38), showlegend=False, title=f"ACTIVITY COMPLETION BY AREA · {area}", yaxis_title="Activity Completion %")
        fig.update_yaxes(range=[0, ymax], ticksuffix="%", gridcolor=GRID)
        fig.update_xaxes(tickangle=-25)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if "Electrical Infrastructure & Equipment" in set(df["Area"].astype(str)):
        st.caption("Electrical Infrastructure & Equipment is a dashboard-derived category for HELIX activities without a QTS-DASH assignment; the original XER coding remains unchanged.")
    render_lineups_detail(m, area)


def render_lineups_detail(m: DC7Model, area: str):
    df = m.lineup_stats(area)
    if df.empty:
        return
    st.markdown(f'<div class="section-caption">EQUIPMENT LINE-UPS PROGRESS DETAIL · {area}</div>', unsafe_allow_html=True)
    st.markdown('<div class="small-note">Activity-count status for Equipment Line-Ups identified from the Gallery line-up activity naming structure. Activity Completion % = Completed / Tasks.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1], gap="large")
    with c1:
        h = f'<div class="panel"><div class="panel-head"><div class="panel-title">{area} · SUMMARY BY LINE-UP</div></div><table class="detail-table"><thead><tr><th>Line-Up</th><th>Tasks</th><th>Activity Completion %</th><th>Not Started</th><th>In Progress</th><th>Completed</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            h += f'<tr><td>{_safe(r["Line-Up"])}</td><td>{int(r.Tasks)}</td><td>{r["Activity Completion %"]:.1f}%</td><td>{int(r["Not Started"])}</td><td>{int(r["In Progress"])}</td><td>{int(r.Completed)}</td></tr>'
        st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    with c2:
        fig = go.Figure(go.Bar(x=df["Line-Up"], y=df["Activity Completion %"], customdata=df[["Tasks", "Completed", "In Progress", "Not Started"]], text=[f"{x:.1f}%" for x in df["Activity Completion %"]], textposition="outside", marker=dict(color="#1f6d8a"), hovertemplate="<b>%{x}</b><br>Completion: %{y:.1f}%<br>Tasks: %{customdata[0]}<br>Completed: %{customdata[1]}<br>In Progress: %{customdata[2]}<br>Not Started: %{customdata[3]}<extra></extra>"))
        ymax = max(10, float(df["Activity Completion %"].max()) * 1.35 + 1) if not df.empty else 10
        fig.update_layout(**_layout(410, 70, 70, 38), showlegend=False, title=dict(text=f"ACTIVITY COMPLETION BY LINE-UP · {area}", x=0.01, xanchor="left"), yaxis_title="Activity Completion %")
        fig.update_yaxes(range=[0, ymax], ticksuffix="%", gridcolor=GRID)
        fig.update_xaxes(tickangle=-20)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_gate_table(reg: pd.DataFrame):
    h = '<div class="gate-wrap"><table class="gate-table"><thead><tr><th>Control Gate</th><th>Activity ID</th><th>Area</th><th>Gate Type</th><th>Status</th><th>Baseline Date</th><th>Current Date</th><th>Finish Variance</th><th>Total Float</th></tr></thead><tbody>'
    for _, r in reg.iterrows():
        v = r["Finish Variance"]; tf = r["Total Float"]
        vc = "var-early" if pd.notna(v) and v > 0 else ("var-late" if pd.notna(v) and v < 0 else "var-zero")
        tc = "tf-neg" if pd.notna(tf) and tf < 0 else ("tf-pos" if pd.notna(tf) and tf > 0 else "tf-zero")
        h += f'<tr><td>{_safe(r["Control Gate"])}</td><td>{_safe(r["Activity ID"])}</td><td>{_safe(r["Area"])}</td><td>{_safe(r["Gate Type"])}</td><td>{_safe(r["Status"])}</td><td>{_fmt_date(r["Baseline Date"])}</td><td>{_fmt_date(r["Current Date"])}</td><td class="{vc}">{_fmt_days(r["Finish Variance"])}</td><td class="{tc}">{"—" if pd.isna(tf) else f"{tf:+.1f} d"}</td></tr>'
    st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)


def render_gates(m: DC7Model):
    st.markdown('<div class="section-caption">PROJECT CONTROL GATES · FTE READY</div>', unsafe_allow_html=True)
    st.caption("Main DC7 project only · Baseline vs Current. FTE Ready is matched by the IST.6100 activity family inside the tracked DC7 project. Finish Variance = Baseline Date − Current Date. Positive = ahead, negative = late, zero = no change.")
    st.markdown(
        '''<div class="gate-legend">
          <span class="item"><span class="diamond"></span>Baseline FTE Ready</span>
          <span class="item"><span class="dot"></span>Current FTE Ready</span>
          <span class="item"><span class="line-late"></span>Later than Baseline (− days)</span>
          <span class="item"><span class="line-early"></span>Earlier than Baseline (+ days)</span>
          <span class="item"><span class="line-zero"></span>No change (0 days)</span>
        </div>''',
        unsafe_allow_html=True,
    )

    reg = m.fte_ready_comparison().copy()
    if reg.empty:
        st.info("No comparable FTE Ready milestones were identified in the DC7 main project.")
        return

    f1, f2 = st.columns([1, 1], gap="small")
    area_sel = f1.selectbox("Data Hall", ["All"] + reg["Area"].astype(str).tolist(), index=0, key="fte_gate_area")
    variance_sel = f2.selectbox("Variance", ["All", "Late", "Ahead", "No Change"], index=0, key="fte_gate_var")
    view = reg.copy()
    if area_sel != "All":
        view = view[view["Area"].eq(area_sel)]
    if variance_sel == "Late":
        view = view[view["Finish Variance (d)"] < 0]
    elif variance_sel == "Ahead":
        view = view[view["Finish Variance (d)"] > 0]
    elif variance_sel == "No Change":
        view = view[view["Finish Variance (d)"].fillna(999999).eq(0)]

    fig = go.Figure()
    view = view.sort_values("Area").reset_index(drop=True)
    yvals = list(range(len(view) - 1, -1, -1))
    dates = []
    for y, (_, r) in zip(yvals, view.iterrows()):
        b = r["Baseline Date"]
        c = r["Current Date"]
        v = r["Finish Variance (d)"]
        tf = r.get("Total Float (d)", pd.NA)
        dates += [x for x in [b, c] if pd.notna(x)]
        col = _timeline_color(v)

        if pd.notna(b) and pd.notna(c):
            fig.add_trace(go.Scatter(
                x=[b, c], y=[y, y], mode="lines",
                line=dict(color=col, width=8), showlegend=False, hoverinfo="skip"
            ))
        if pd.notna(b):
            fig.add_trace(go.Scatter(
                x=[b], y=[y], mode="markers",
                marker=dict(symbol="diamond", size=12, color="#7048c7"),
                showlegend=False,
                hovertemplate=f"<b>{_safe(r['Area'])} · Baseline FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(b)}<extra></extra>"
            ))
        if pd.notna(c):
            tf_txt = "—" if pd.isna(tf) else f"{float(tf):+.1f} d"
            fig.add_trace(go.Scatter(
                x=[c], y=[y], mode="markers",
                marker=dict(size=12, color=col), showlegend=False,
                hovertemplate=f"<b>{_safe(r['Area'])} · Current FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(c)}<br>Finish Variance: {_fmt_days(v)}<br>Total Float: {tf_txt}<br>Status: {_safe(r['Status'])}<extra></extra>"
            ))
            fig.add_annotation(
                x=c, y=y, text=_fmt_days(v), showarrow=False,
                xanchor="left", xshift=9,
                font=dict(size=13, color=col)
            )

    if dates:
        fig.update_xaxes(
            type="date",
            range=[min(dates) - pd.Timedelta(days=20), max(dates) + pd.Timedelta(days=35)],
            dtick="M1", tickformat="%b\n%Y", gridcolor=GRID, title="Milestone Date"
        )
    if pd.notna(m.data_date):
        fig.add_vline(
            x=m.data_date, line_dash="dash", line_color="#62788e",
            annotation_text=f"Data Date · {_fmt_date(m.data_date)}", annotation_position="top right"
        )
    fig.update_yaxes(
        tickmode="array", tickvals=yvals, ticktext=view["Area"].tolist(),
        gridcolor=GRID, zeroline=False, tickfont=dict(size=13)
    )
    fig.update_layout(
        **_layout(max(360, 62 * len(view) + 120), 105, 60, 30),
        showlegend=False, title=dict(text="")
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    audit = view[["Area", "Activity ID", "Activity Name", "Baseline Date", "Current Date", "Finish Variance (d)", "Total Float (d)", "Status"]].copy()
    audit["Baseline Date"] = audit["Baseline Date"].apply(_fmt_date)
    audit["Current Date"] = audit["Current Date"].apply(_fmt_date)
    audit["Finish Variance"] = audit["Finish Variance (d)"].apply(_fmt_days)
    audit["Total Float"] = audit["Total Float (d)"].apply(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} d")
    audit = audit.drop(columns=["Finish Variance (d)", "Total Float (d)"])
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.caption("Control gates are restricted to FTE Ready milestones from the DC7 main project. External projects and cross-project relationships are excluded.")

def render_dashboard(m: DC7Model):
    render_header(m)
    render_kpis(m)
    render_scurve_and_status(m)
    render_windows(m)
    render_stats(m)
    render_progress_detail(m)
    render_gates(m)
    with st.expander("Diagnostics · DC7 XER / HELIX Scope Audit", expanded=False):
        d = m.diagnostics()
        st.dataframe(pd.DataFrame([d]), use_container_width=True, hide_index=True)
        st.caption("Scope rule: current HELIX activities are selected by Activity Code QTS - Subcontractor = HELIX. Baseline scope is matched 1:1 by task_code. Areas use QTS - AREA; progress detail uses QTS - DASH. FTE Ready compares the matched main-project IST.6100 Baseline/Current milestones only; external projects and external relationships are excluded. Project Control Gates are restricted to the six main-project FTE Ready IST.6100 milestones, matched Baseline vs Current by exact task_code.")
