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
#MainMenu{{visibility:hidden}} footer{{visibility:hidden}} header[data-testid="stHeader"]{{display:none!important}}
[data-testid="stToolbar"]{{display:none!important}} [data-testid="stSidebar"]{{display:none!important}} [data-testid="collapsedControl"]{{display:none!important}}
.block-container{{padding-top:.6rem;padding-bottom:2rem;max-width:1680px}} [data-testid="stAppViewContainer"]{{background:#fff}}
html,body,[class*="css"]{{font-family:Arial,Helvetica,sans-serif;color:{TEXT}}} [data-testid="stVerticalBlock"]{{gap:.55rem}}
.helix-header{{display:grid;grid-template-columns:minmax(170px,0.9fr) minmax(0,5fr) minmax(170px,0.9fr);gap:12px;align-items:stretch;background:#fff;color:{TEXT};min-height:108px;width:100%}}
.helix-header .logo-card{{background:#fff;border:1px solid {BORDER};border-radius:7px;padding:10px 12px;min-width:0;min-height:108px;display:flex;align-items:center;justify-content:center}}
.helix-header .logo-card img{{display:block;width:100%;height:80px;max-height:80px;object-fit:contain}}
.helix-header .header-main{{background:{NAVY};color:#fff;border-radius:7px;min-width:0;padding:18px 24px;display:flex;align-items:center;justify-content:space-between;gap:18px}}
.helix-header .header-title-block{{min-width:0;flex:1 1 auto}}
.helix-header .brand-title{{font-size:clamp(18px,1.55vw,26px);font-weight:850;line-height:1.13}}
.helix-header .brand-subtitle{{font-size:13px;font-weight:600;margin-top:8px;color:#d7e2ed}}
.helix-header .header-center{{display:flex;gap:7px;align-items:center;white-space:nowrap;flex:0 0 auto}}
.helix-header .header-chip{{border:1px solid #879cb3;border-radius:6px;padding:10px 12px;font-size:11px;font-weight:850}}
.helix-header .header-meta{{text-align:right;white-space:nowrap;line-height:1.35;flex:0 0 auto}}
.helix-header .header-meta .line{{font-size:11px;font-weight:700;margin:3px 0}}
.helix-header .header-meta .value{{font-size:12px;font-weight:900}}
@media(max-width:1220px){{.helix-header{{grid-template-columns:minmax(120px,0.85fr) minmax(0,5fr) minmax(120px,0.85fr);gap:7px}}.helix-header .header-main{{flex-wrap:wrap;gap:9px;padding:14px}}.helix-header .header-meta{{text-align:left}}.helix-header .logo-card{{min-height:100px}}.helix-header .logo-card img{{height:70px}}}}
@media(max-width:700px){{.helix-header{{grid-template-columns:1fr 1fr}}.helix-header .header-main{{grid-column:1/-1;grid-row:1}}.helix-header .logo-card{{min-height:65px}}.helix-header .logo-card img{{height:52px}}.helix-header .header-center{{flex-wrap:wrap}}.helix-header .header-meta{{white-space:normal}}}}
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
@media(max-width:1280px){{.helix-header{{grid-template-columns:112px minmax(260px,1fr) 190px 230px 130px;column-gap:10px}}.brand-title{{font-size:20px}}.logo-card{{height:66px}}.logo-card img{{height:58px;max-height:58px}}.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:990px){{.helix-header{{grid-template-columns:112px minmax(0,1fr) 132px;row-gap:12px}}.helix-header>.logo-card:last-child{{grid-column:3;grid-row:1}}.helix-header>.header-center{{grid-column:1/3;grid-row:2;justify-content:flex-start}}.helix-header>.header-meta{{grid-column:3;grid-row:2}}.brand-title{{font-size:19px;white-space:normal}}.header-meta .line{{font-size:10px}}.header-meta .value{{font-size:11px}}}}
.schedule-view-caption{{font-size:14px;font-weight:750;color:#15253b;margin:4px 0 9px 2px}}
.header-nav-clearance{{display:block;clear:both;height:22px;width:100%}}
[data-testid="stSegmentedControl"]{{display:flex;justify-content:center}}
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
                p=m[0]
                ext=p.suffix.lower()
                mime="image/jpeg" if ext in {".jpg", ".jpeg"} else ("image/webp" if ext==".webp" else "image/png")
                encoded=base64.b64encode(p.read_bytes()).decode("ascii")
                return f"data:{mime};base64,{encoded}"
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


def render_header(m: DC7Model, view: str):
    if view == "SUFFOLK":
        date_label, date_value = "Latest Data Date", _fmt_date(m.data_date)
        current_label, current_value = "Current Update", m.update_path.stem
        source_label = "SUFFOLK · HELIX Construction"
    else:
        # Never substitute Suffolk Current-C for independent HELIX U01.
        current_source = m.auxiliary_update_project
        date_label = "Latest Data Date"
        date_value = _fmt_date(pd.to_datetime(
            current_source.get("last_recalc_date") if current_source is not None else None,
            errors="coerce",
        ))
        current_label, current_value = "Current Update", "226021-HE.U01"
        source_label = "HELIX Electrical Line-Ups & MOH"

    st.markdown(f"""
    <div class="helix-header">
      <div class="logo-card"><img src="{_logo('helix')}" alt="HELIX Electric"></div>
      <div class="header-main">
        <div class="header-title-block"><div class="brand-title">{BRAND_NAME} {APP_TITLE}</div><div class="brand-subtitle">{APP_SUBTITLE}</div></div>
        <div class="header-center"><span class="header-chip">DC7 PROJECT DETAIL</span><span class="header-chip">v{VERSION}</span></div>
        <div class="header-meta">
          <div class="line">{_safe(date_label)}&nbsp;&nbsp;<span class="value">{_safe(date_value)}</span></div>
          <div class="line">{_safe(current_label)}&nbsp;&nbsp;<span class="value">{_safe(current_value)}</span></div>
        </div>
      </div>
      <div class="logo-card"><img src="{_logo('toro')}" alt="TORO Project Management Consultants"></div>
    </div>
    <div class="header-nav-clearance" aria-hidden="true"></div>
    """, unsafe_allow_html=True)


def render_kpis(m: DC7Model, view: str):
    fv = m.finish_variance_days
    counts = m.status_counts()
    p = m.status_percentages()
    st.markdown('<div class="section-caption">PROJECT STATUS SUMMARY</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="panel schedule"><div class="panel-head"><div><span class="time-pill">TIME</span><span class="panel-title">SCHEDULE PERFORMANCE</span></div></div>', unsafe_allow_html=True)
    cards = [
        ("Baseline Completion", _fmt_date(m.baseline_finish), m.baseline_path.stem, ""),
        ("Current Forecast Finish", _fmt_date(m.current_finish), m.update_path.stem, _var_class(fv)),
        ("Finish Date Shift", _fmt_days(fv), "", _var_class(fv)),
        ("Completed Activities", _fmt_pct(p["Completed %"]), "", "good" if p["Completed %"] > 0 else ""),
        ("In Progress Activities", _fmt_pct(p["In Progress %"]), "", "neutral" if p["In Progress %"] > 0 else ""),
        ("Not Started Activities", _fmt_pct(p["Not Started %"]), "", "bad" if p["Not Started %"] > 0 else ""),
        ("Total Activities", f"{counts['Total']:,}", "", ""),
        ("Current Data Date", _fmt_date(m.data_date), "", ""),
    ]
    h = '<div class="kpi-grid">'
    for a, b, c, d in cards:
        h += f'<div class="kpi"><div class="label">{_safe(a)}</div><div class="value {d}">{_safe(b)}</div><div class="sub">{_safe(c)}</div></div>'
    st.markdown(h + '</div></div>', unsafe_allow_html=True)



def render_helix_kpis(m: DC7Model):
    """Independent electrical BL/U01 schedule performance, no SUFFOLK rows."""
    from src.helix_baseline import helix_bl_current_overview
    bl, cur = m.independent_helix_baseline(), m.independent_helix_update()
    st.markdown('<div class="section-caption">PROJECT STATUS SUMMARY</div>', unsafe_allow_html=True)
    if bl is None or cur is None:
        st.warning("Independent HELIX BL and U01 are both required.")
        return
    info, _ = helix_bl_current_overview(
        bl, cur, m.auxiliary_update_project["last_recalc_date"]
    )
    count = info["Counts"]
    total = count["Total"]
    pct = lambda key: f"{100 * count[key] / total:.2f}%"
    shift = info["Finish Shift (calendar days)"]
    st.markdown(
        '<div class="panel schedule"><div class="panel-head">'
        '<div><span class="time-pill">TIME</span>'
        '<span class="panel-title">SCHEDULE PERFORMANCE</span></div>'
        '</div>', unsafe_allow_html=True,
    )
    cards = [
        ("Baseline Completion", _fmt_date(info["Baseline Finish"]), "226021-HE.B", ""),
        ("Current Forecast Finish", _fmt_date(info["Current Finish"]), "226021-HE.U01", ""),
        ("Finish Date Shift", f"{shift:+d} days", "", _var_class(shift)),
        ("Completed Activities", pct("Completed"), "", ""),
        ("In Progress Activities", pct("In Progress"), "", ""),
        ("Not Started Activities", pct("Not Started"), "", ""),
        ("Total Activities", f"{total:,}", "", ""),
        ("Current Data Date", _fmt_date(info["Current Data Date"]), "", ""),
    ]
    h = '<div class="kpi-grid">'
    for label, value, sub, css in cards:
        h += (
            f'<div class="kpi"><div class="label">{_safe(label)}</div>'
            f'<div class="value {css}">{_safe(value)}</div>'
            f'<div class="sub">{_safe(sub)}</div></div>'
        )
    st.markdown(h + '</div></div>', unsafe_allow_html=True)


def render_helix_baseline_scurve_and_status(m: DC7Model):
    """HELIX BL vs independent U01 forecast and actual activity completions."""
    from src.helix_baseline import helix_bl_current_overview
    bl, cur = m.independent_helix_baseline(), m.independent_helix_update()
    st.markdown('<div class="section-caption">SCHEDULE PERFORMANCE</div>', unsafe_allow_html=True)
    if bl is None or cur is None:
        st.warning("Independent HELIX BL and U01 are both required for progress S-curve.")
        return
    info, curve = helix_bl_current_overview(bl, cur, m.auxiliary_update_project["last_recalc_date"])
    count = info["Counts"]
    total = count["Total"]
    c1, c2 = st.columns([1.7, 0.8], gap="large")
    with c1:
        st.markdown(
            '<div class="panel"><div class="panel-head">'
            '<div class="panel-title">PROGRESS S-CURVE</div>'
            '<div class="panel-note">HELIX Electrical Line-Ups & MOH · activity count</div>'
            '</div>', unsafe_allow_html=True,
        )
        fig = go.Figure()
        for field, color in (
            ("Baseline Planned Activities", "#4B91F1"),
            ("Current Forecast Activities", "#59BA75"),
            ("Actual Completed Activities", "#F28A58"),
        ):
            actual = field == "Actual Completed Activities"
            fig.add_trace(go.Scatter(
                x=curve["Date"], y=curve[field], name=field,
                mode="lines+markers" if actual else "lines",
                line=dict(color=color, width=3),
                marker=dict(size=5 if actual else 0),
                connectgaps=False,
                hovertemplate=f"%{{x|%d-%b-%Y}}<br>%{{y:,.0f}} {field}<extra></extra>",
            ))
        dd = info["Current Data Date"]
        fig.add_vline(
            x=dd, line_dash="dash", line_color="#6d7f92",
            annotation_text=f"Data Date · {_fmt_date(dd)}",
            annotation_position="top right",
        )
        fig.update_layout(
            **_layout(440, 54, 100, 42), title=dict(text=""),

            yaxis_title="Cumulative Activities", xaxis_title="Date",
            legend_title_text="",
        )
        fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.27, xanchor="center", x=0.5, font=dict(size=11)))
        fig.update_yaxes(range=[0, total * 1.05], tickformat=",d", gridcolor=GRID)
        fig.update_xaxes(type="date", dtick="M1", tickformat="%b\n%Y", gridcolor=GRID)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(
            '<div class="panel"><div class="panel-head">'
            '<div class="panel-title">OVERALL ACTIVITY STATUS</div>'
            '</div>', unsafe_allow_html=True,
        )
        h = '<div class="activity-wrap">'
        for label in ("Total", "Completed", "In Progress", "Not Started"):
            h += f'<div class="activity-card"><div class="num">{count[label]:,}</div><div class="lab">{label}</div></div>'
        ratio = lambda k: f'{100 * count[k] / total:.2f}%'
        h += ('</div><div class="scope-note">'
              f'Completed: <b>{ratio("Completed")}</b><br>'
              f'In Progress: <b>{ratio("In Progress")}</b><br>'
              f'Not Started: <b>{ratio("Not Started")}</b>'
              '</div></div>')
        st.markdown(h, unsafe_allow_html=True)


def render_scurve_and_status(m: DC7Model):
    st.markdown('<div class="section-caption">SCHEDULE PERFORMANCE</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.7, 0.8], gap="large")
    with c1:
        st.markdown('<div class="panel"><div class="panel-head"><div class="panel-title">PROGRESS S-CURVE</div><div class="panel-note">Cumulative activity count · baseline / current forecast / actual completions</div></div>', unsafe_allow_html=True)
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
        h += f'</div><div class="scope-note">Completed: <b>{p["Completed %"]:.1f}%</b><br>In Progress: <b>{p["In Progress %"]:.1f}%</b><br>Not Started: <b>{p["Not Started %"]:.1f}%</b></div></div>'
        st.markdown(h, unsafe_allow_html=True)


def render_windows(m: DC7Model):
    st.markdown('<div class="section-caption">SCHEDULE SUMMARY · BASELINE VS CURRENT UPDATE</div>', unsafe_allow_html=True)
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
            v = r["Finish Date Shift (d)"]; col = _timeline_color(v)
            fig.add_trace(go.Scatter(x=[cs, cf], y=[cur_y, cur_y], mode="lines+markers", line=dict(color=col, width=9), marker=dict(size=9, color=col), showlegend=False, hovertemplate=f"<b>{r.Area} · Current</b><br>Earliest HELIX Start: {_fmt_date(cs)}<br>Latest HELIX Finish: {_fmt_date(cf)}<br>Start Date Shift: {_fmt_days(r['Start Date Shift (d)'])}<br>Finish Date Shift: {_fmt_days(v)}<extra></extra>"))
            fig.add_annotation(x=cf, y=cur_y, text=_fmt_days(v), showarrow=False, xanchor="left", xshift=8, font=dict(size=12, color=col))
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
    st.markdown('<div class="small-note">Main DC7 project only. Gray diamond = Baseline FTE Ready. Colored circle = Current FTE Ready. Date Shift = Baseline − Current. Green/positive = earlier than Baseline, red/negative = later than Baseline, blue/zero = no date change. No external-project milestones or external relationships are used.</div>', unsafe_allow_html=True)
    df = m.fte_ready_comparison()
    if df.empty:
        st.info("No active FTE Ready milestones remain in Construction. The previous IST.6100 family has been archived in P6; consult the Activity Audit for their IDs.")
        return

    fig = go.Figure()
    yvals = list(range(len(df) - 1, -1, -1))
    dates = []
    for y, (_, r) in zip(yvals, df.iterrows()):
        bd, cd = r["Baseline Date"], r["Current Date"]
        v = r["Finish Date Shift (d)"]
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
                hovertemplate=f"<b>{r['Area']} · Current FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(cd)}<br>Finish Date Shift: {_fmt_days(v)}<br>Status: {_safe(r['Status'])}<extra></extra>"
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
    audit = df[["Area", "Activity ID", "Baseline Date", "Current Date", "Finish Date Shift (d)", "Status"]].copy()
    audit["Baseline Date"] = audit["Baseline Date"].apply(_fmt_date)
    audit["Current Date"] = audit["Current Date"].apply(_fmt_date)
    audit["Finish Date Shift"] = audit["Finish Date Shift (d)"].apply(_fmt_days)
    audit = audit.drop(columns=["Finish Date Shift (d)"])
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.caption("Source: DC7 main project only. FTE Ready is matched by the IST.6100 activity family in Baseline and Current. External projects and cross-project relationships are excluded from this dashboard.")


def render_stats(m: DC7Model, title: str):
    st.markdown(f'<div class="section-caption">{_safe(title)}</div>', unsafe_allow_html=True)
    df = m.area_stats().copy()
    if df.empty:
        st.info("No area-coded activities found.")
        return
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        h = '<div class="panel"><table class="stats-table"><thead><tr><th>Area</th><th>Total Activities</th><th>Activity Completion %</th><th>Completed</th><th>In Progress</th><th>Not Started</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            h += f'<tr><td>{_safe(r.Area)}</td><td>{int(r["Total Tasks"]):,}</td><td>{r["Activity Completion %"]:.1f}%</td><td>{int(r.Completed)}</td><td>{int(r["In Progress"])}</td><td>{int(r["Not Started"])}</td></tr>'
        st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    with right:
        fig = go.Figure(go.Bar(x=df["Activity Completion %"], y=df.Area, orientation="h", text=[f"{x:.1f}%" for x in df["Activity Completion %"]], textposition="outside", textfont=dict(size=13, color=TEXT), marker=dict(color="#1f6d8a")))
        fig.update_layout(**_layout(max(355, 44 * len(df) + 95), 90, 40, 28), showlegend=False, xaxis_title="Activity Completion %", yaxis_title="", title="OVERALL % COMPLETE")
        fig.update_xaxes(range=[0, max(10, float(df["Activity Completion %"].max()) * 1.35 + 1)], ticksuffix="%", gridcolor=GRID)
        fig.update_yaxes(autorange="reversed", gridcolor="#fff")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_progress_detail(m: DC7Model, view: str):
    st.markdown('<div class="section-caption">PROJECT PROGRESS DETAIL</div>', unsafe_allow_html=True)
    area = st.selectbox("Area / Data Hall", m.areas(), index=0, key=f"dc7_area_{view.lower()}")
    consolidated = view == "HELIX" and area.upper().startswith("DH")
    p6_wbs = view == "SUFFOLK" and area in ("FOH", "BOH")
    dh_p6_wbs = view == "SUFFOLK" and area in (
        "DH1100", "DH1200", "DH1300", "DH1400", "DH1500", "DH1600"
    )
    df = (
        m.wbs_area_stats(area) if p6_wbs
        else m.data_hall_wbs_stats(area) if dh_p6_wbs
        else m.subarea_stats(area, helix_display=consolidated)
    )
    # SUFFOLK FOH/BOH display alias only: preserve the P6 WBS, task mapping,
    # original activity audit and every numeric result unchanged.
    if p6_wbs:
        df = df.copy()
        df["Area"] = df["Area"].replace({"Priority Walls": "Priority Rooms"})
    c1, c2 = st.columns([1.15, 1], gap="large")
    with c1:
        summary_title = ("SUMMARY BY P6 WBS" if p6_wbs or dh_p6_wbs else
                         "FUNCTIONAL PACKAGE SUMMARY" if area == "MOH" else
                         "SUMMARY BY FUNCTIONAL GROUP" if consolidated else
                         "SUMMARY BY QTS - DASH")
        first_column = "P6 WBS GROUP" if p6_wbs or dh_p6_wbs else "Area"
        h = f'<div class="panel"><div class="panel-head"><div class="panel-title">{area} · {summary_title}</div></div><table class="detail-table"><thead><tr><th>{first_column}</th><th>Total Activities</th><th>Activity Completion %</th><th>Not Started</th><th>In Progress</th><th>Completed</th></tr></thead><tbody>'
        for _, r in df.iterrows():
            label = _safe(r.Area)
            h += f'<tr><td>{label}</td><td>{int(r.Tasks)}</td><td>{r["Activity Completion %"]:.1f}%</td><td>{int(r["Not Started"])} </td><td>{int(r["In Progress"])} </td><td>{int(r.Completed)}</td></tr>'
        st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    with c2:
        fig = go.Figure(go.Bar(x=df.Area, y=df["Activity Completion %"], text=[f"{x:.1f}%" for x in df["Activity Completion %"]], textposition="outside", textfont=dict(size=13, color=TEXT), marker=dict(color="#1f6d8a")))
        ymax = max(10, float(df["Activity Completion %"].max()) * 1.35 + 1) if not df.empty else 10
        chart_title = (f"ACTIVITY COMPLETION BY WBS · {area}" if p6_wbs or dh_p6_wbs else
                       f"ACTIVITY COMPLETION · {area}" if area == "MOH" else
                       f"ACTIVITY COMPLETION BY AREA · {area}")
        fig.update_layout(
            **_layout(480 if dh_p6_wbs else 410, 70, 165 if dh_p6_wbs else 115, 38),
            showlegend=False, title=chart_title, yaxis_title="Activity Completion %"
        )
        fig.update_yaxes(range=[0, ymax], ticksuffix="%", gridcolor=GRID)
        # Horizontal category labels with line wrapping to avoid collisions.
        labels = df["Area"].astype(str).tolist()
        wrapped_labels = [
            "Commissioning &<br>Start Up" if x == "Commissioning & Start Up" else
            "Energization, Start-up<br>& Commissioning" if x == "Energization, Start-up & Commissioning" else
            "Electrical<br>Rooms" if x == "Electrical Rooms" else
            "Mechanical<br>Yard" if x == "Mechanical Yard" else
            "Electrical<br>Yard" if x == "Electrical Yard" else
            "Priority<br>Rooms" if x == "Priority Rooms" else
            "Other<br>Rooms" if x == "Other Rooms" else x
            for x in labels
        ]
        fig.update_xaxes(tickangle=0, tickmode="array", tickvals=labels,
                         ticktext=wrapped_labels, automargin=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    # Original WBS and out-of-scope audit remain verified internally.

    # Dedicated HELIX Line-Ups are rendered separately in HELIX VIEW only.


def render_lineups_detail(m: DC7Model, area: str):
    df = m.lineup_stats(area)
    if df.empty:
        return
    st.markdown(f'<div class="section-caption">EQUIPMENT LINE-UPS · HELIX BASELINE · {area}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">Only source: official independent HELIX baseline '
        '226021-HE.B.xer. These are baseline activity statuses, '
        'not a measured HELIX Current or current project progress.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1.15, 1], gap="large")
    with c1:
        h = f'<div class="panel"><div class="panel-head"><div class="panel-title">{area} · SUMMARY BY LINE-UP</div></div><table class="detail-table"><thead><tr><th>Line-Up</th><th>Total Activities</th><th>Activity Completion %</th><th>Not Started</th><th>In Progress</th><th>Completed</th></tr></thead><tbody>'
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
    h = '<div class="gate-wrap"><table class="gate-table"><thead><tr><th>Milestone</th><th>Activity ID</th><th>Area</th><th>Milestone Type</th><th>Status</th><th>Baseline Date</th><th>Current Date</th><th>Finish Date Shift</th><th>Total Float</th></tr></thead><tbody>'
    for _, r in reg.iterrows():
        v = r["Finish Date Shift"]; tf = r["Total Float"]
        vc = "var-early" if pd.notna(v) and v > 0 else ("var-late" if pd.notna(v) and v < 0 else "var-zero")
        tc = "tf-neg" if pd.notna(tf) and tf < 0 else ("tf-pos" if pd.notna(tf) and tf > 0 else "tf-zero")
        h += f'<tr><td>{_safe(r["Milestone"])}</td><td>{_safe(r["Activity ID"])}</td><td>{_safe(r["Area"])}</td><td>{_safe(r["Milestone Type"])}</td><td>{_safe(r["Status"])}</td><td>{_fmt_date(r["Baseline Date"])}</td><td>{_fmt_date(r["Current Date"])}</td><td class="{vc}">{_fmt_days(r["Finish Date Shift"])}</td><td class="{tc}">{"—" if pd.isna(tf) else f"{tf:+.1f} d"}</td></tr>'
    st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)


def render_gates(m: DC7Model):
    st.markdown('<div class="section-caption">PROJECT KEY MILESTONES · FTE READY</div>', unsafe_allow_html=True)
    st.caption("Main DC7 project only · Baseline vs Current. FTE Ready is matched by the IST.6100 activity family inside the tracked DC7 project. Finish Date Shift = Baseline Date − Current Date. Positive = earlier than Baseline, negative = later than Baseline, zero = no date change.")
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
        st.info("No active FTE Ready milestones remain in Construction. The previous IST.6100 family has been archived in P6; consult the Activity Audit for their IDs.")
        return

    f1, f2 = st.columns([1, 1], gap="small")
    area_sel = f1.selectbox("Data Hall", ["All"] + reg["Area"].astype(str).tolist(), index=0, key="fte_gate_area")
    shift_sel = f2.selectbox("Date Shift", ["All", "Late", "Ahead", "No Change"], index=0, key="fte_gate_var")
    view = reg.copy()
    if area_sel != "All":
        view = view[view["Area"].eq(area_sel)]
    if shift_sel == "Late":
        view = view[view["Finish Date Shift (d)"] < 0]
    elif shift_sel == "Ahead":
        view = view[view["Finish Date Shift (d)"] > 0]
    elif shift_sel == "No Change":
        view = view[view["Finish Date Shift (d)"].fillna(999999).eq(0)]

    fig = go.Figure()
    view = view.sort_values("Area").reset_index(drop=True)
    yvals = list(range(len(view) - 1, -1, -1))
    dates = []
    for y, (_, r) in zip(yvals, view.iterrows()):
        b = r["Baseline Date"]
        c = r["Current Date"]
        v = r["Finish Date Shift (d)"]
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
                hovertemplate=f"<b>{_safe(r['Area'])} · Current FTE Ready</b><br>Activity ID: {_safe(r['Activity ID'])}<br>Date: {_fmt_date(c)}<br>Finish Date Shift: {_fmt_days(v)}<br>Total Float: {tf_txt}<br>Status: {_safe(r['Status'])}<extra></extra>"
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

    audit = view[["Area", "Activity ID", "Activity Name", "Baseline Date", "Current Date", "Finish Date Shift (d)", "Total Float (d)", "Status"]].copy()
    audit["Baseline Date"] = audit["Baseline Date"].apply(_fmt_date)
    audit["Current Date"] = audit["Current Date"].apply(_fmt_date)
    audit["Finish Date Shift"] = audit["Finish Date Shift (d)"].apply(_fmt_days)
    audit["Total Float"] = audit["Total Float (d)"].apply(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} d")
    audit = audit.drop(columns=["Finish Date Shift (d)", "Total Float (d)"])
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.caption("Key milestones are restricted to FTE Ready milestones from the DC7 main project. External projects and cross-project relationships are excluded.")

def render_helix_lineup_stats(m: DC7Model):
    """Suffolk-style activity status panel for the standalone HELIX baseline.

    Same visual language as SUFFOLK PROJECT STATS, but independent P6
    baseline status is NOT the live project progress from SUFFOLK.
    """
    from src.helix_baseline import lineup_area_status_summary

    data = m.independent_helix_update()
    df = lineup_area_status_summary(data)
    st.markdown(
        '<div class="section-caption">PROGRESS SUMMARY BY AREA</div>',
        unsafe_allow_html=True,
    )
    if data is None:
        st.info("Official HELIX U01 required.")
        return

    def percent_label(value: float) -> str:
        # Display small, non-zero completion rates rather than rounding them
        # to 0.0%, particularly the project-wide 2 / 4153 activities.
        return f"{value:.2f}%" if 0 < value < 1 else f"{value:.1f}%"

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        h = (
            '<div class="panel"><table class="stats-table"><thead><tr>'
            '<th>Area</th><th>Total Activities</th><th>Activity Completion %</th>'
            '<th>Completed</th><th>In Progress</th><th>Not Started</th>'
            '</tr></thead><tbody>'
        )
        for _, record in df.iterrows():
            h += (
                f'<tr><td>{_safe(record["Area"])}</td>'
                f'<td>{int(record["Total Tasks"]):,}</td>'
                f'<td>{percent_label(float(record["Activity Completion %"]))}</td>'
                f'<td>{int(record["Completed"]):,}</td>'
                f'<td>{int(record["In Progress"]):,}</td>'
                f'<td>{int(record["Not Started"]):,}</td></tr>'
            )
        total_tasks = int(df["Total Tasks"].sum())
        completed = int(df["Completed"].sum())
        in_progress = int(df["In Progress"].sum())
        not_started = int(df["Not Started"].sum())
        if total_tasks != completed + in_progress + not_started:
            raise ValueError("HELIX U01 status totals do not reconcile")
        st.markdown(h + '</tbody></table></div>', unsafe_allow_html=True)
    with right:
        fig = go.Figure(go.Bar(
            x=df["Activity Completion %"],
            y=df["Area"],
            orientation="h",
            text=[percent_label(float(v)) for v in df["Activity Completion %"]],
            textposition="outside",
            textfont=dict(size=13, color=TEXT),
            marker=dict(color="#1f6d8a"),
            hovertemplate="%{y}<br>U01 completed: %{x:.3f}%<extra></extra>",
        ))
        highest = float(df["Activity Completion %"].max()) if not df.empty else 0.0
        fig.update_layout(
            **_layout(max(355, 44 * len(df) + 95), 90, 40, 28),
            showlegend=False,
            xaxis_title="Activity Completion %",
            yaxis_title="",
            title="OVERALL % COMPLETE",
        )
        fig.update_xaxes(
            range=[0, max(1.0, highest * 1.35 + 0.2)],
            ticksuffix="%", gridcolor=GRID,
        )
        fig.update_yaxes(autorange="reversed", gridcolor="#fff")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_helix_lineups(m: DC7Model):
    """HELIX-only Line-Up/MOH quantities and original P6 baseline statuses.

    Expander labels already identify Data Hall and Electrical/MOH, so
    duplicate parent subtotal rows are deliberately omitted.
    """
    from src.helix_baseline import HALLS, wbs_lineup_hierarchy, lineup_order

    data = m.independent_helix_update()
    st.markdown(
        '<div class="section-caption">DATA HALL / LINE-UP PROGRESS DETAIL</div>',
        unsafe_allow_html=True,
    )

    for area in (*HALLS, "MOH"):
        statuses = wbs_lineup_hierarchy(data, area)
        is_moh = area == "MOH"
        heading = "MOH" if is_moh else f"DH {area[2:]}"
        with st.expander(heading, expanded=(area == "DH1100")):
            table = statuses.copy()
            if data is None:
                st.info("Activity counts and statuses are pending the official HELIX U01.")
            column_config = {
                "Line-Up": st.column_config.TextColumn(
                    "Line-Up" if not is_moh else "MOH Area"
                ),
            }
            for column in ("Total Activities", "Not Started", "In Progress", "Completed"):
                column_config[column] = (
                    st.column_config.NumberColumn(column, format="%d")
                    if data is not None
                    else st.column_config.TextColumn(column)
                )
            if is_moh:
                st.dataframe(
                    table, use_container_width=True, hide_index=True,
                    column_config=column_config,
                )
            else:
                left, right = st.columns([1.14, 1], gap="large")
                with left:
                    st.dataframe(
                        table, use_container_width=True, hide_index=True,
                        height=450, column_config=column_config,
                    )
                with right:
                    if data is None:
                        st.info("The chart is pending the official HELIX U01.")
                    else:
                        if table["Line-Up"].tolist() != list(lineup_order(area)):
                            raise ValueError(f"Line-Up P6 order mismatch: {area}")
                        names = table["Line-Up"].tolist()
                        total_activities = table["Total Activities"].astype(int)
                        completed_activities = table["Completed"].astype(int)
                        if (total_activities <= 0).any():
                            raise ValueError(f"Invalid HELIX Line-Up activity total in {area}")
                        if (completed_activities < 0).any() or (
                            completed_activities > total_activities
                        ).any():
                            raise ValueError(f"Invalid completed activities in HELIX {area}")
                        completion_pct = (completed_activities / total_activities * 100).tolist()
                        pct_labels = [f"{value:.1f}%" for value in completion_pct]
                        fig = go.Figure(go.Bar(
                            y=names, x=completion_pct, orientation="h",
                            marker_color=NAVY2,
                            text=pct_labels, textposition="outside",
                            customdata=list(zip(
                                completed_activities.tolist(), total_activities.tolist()
                            )),
                            hovertemplate=(
                                "%{y}<br>Activity Completion: %{x:.2f}%"
                                "<br>Completed: %{customdata[0]:,} of "
                                "%{customdata[1]:,}<extra></extra>"
                            ),
                        ))
                        fig.update_layout(
                            **_layout(450, 46, 78, 50),
                            title=f"% COMPLETE BY LINE-UP · {area}",
                            showlegend=False,
                            xaxis_title="Activity Completion %",
                        )
                        fig.update_yaxes(
                            autorange="reversed", categoryorder="array",
                            categoryarray=names,
                        )
                        # Keep small nonzero values legible; scale is percent,
                        # not the number of activities or share of the hall.
                        x_max = min(100.0, max(10.0, max(completion_pct) * 1.35))
                        fig.update_xaxes(
                            range=[0, x_max], ticksuffix="%", gridcolor=GRID,
                        )
                        st.plotly_chart(
                            fig, use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"helix_lineup_chart_{area}",
                        )



def render_helix_contract_milestones(m: DC7Model):
    """P6 HELIX BL vs U01 milestone Finish changes, US federal working days.

    Includes HELIX-coded M./IST. activity IDs. Contractual dates in
    Activity Names are displayed separately; five IST names have been
    changed in the official update and are flagged explicitly.
    """
    from src.helix_baseline import us_federal_workday_delay
    baseline = m.independent_helix_baseline()
    current = m.independent_helix_update()
    st.markdown(
        '<div class="section-caption">KEY MILESTONES VARIANCE</div>',
        unsafe_allow_html=True,
    )
    if baseline is None or current is None:
        st.warning("HELIX BL and U01 are required for milestone comparison.")
        return
    bdf = baseline["_contract_milestones"].copy()
    udf = current["_contract_milestones"].copy()
    if len(bdf) != 10 or len(udf) != 10:
        raise ValueError("Unexpected HELIX QC2.2 / IST contractual milestone population")
    df = bdf[["Activity ID", "Area", "Milestone", "Baseline Finish", "Contractual Date"]].merge(
        udf[["Activity ID", "Current Finish", "Contractual Date", "Activity Name"]],
        on="Activity ID", how="outer", suffixes=("_BL", "_U01"), validate="one_to_one",
        indicator=True,
    )
    if not df["_merge"].eq("both").all():
        raise ValueError("HELIX milestone BL/U01 Activity ID mismatch")
    df["Variance (Working Days)"] = df.apply(
        lambda r: us_federal_workday_delay(r["Baseline Finish"], r["Current Finish"]),
        axis=1,
    )
    df["Contract Delay (Working Days)"] = df.apply(
        lambda r: us_federal_workday_delay(r["Contractual Date_U01"], r["Current Finish"]),
        axis=1,
    )
    df["Contract Date Changed"] = (
        df["Contractual Date_BL"].dt.normalize() != df["Contractual Date_U01"].dt.normalize()
    )
    changed = df.loc[df["Contract Date Changed"], "Activity ID"].tolist()
    expected_legacy_ist = {f"IST.{n}" for n in (1200, 1300, 1400, 1500, 1600)}
    if set(changed) not in (set(), expected_legacy_ist):
        raise ValueError(f"Unexpected changes in named contractual dates: {changed}")

    # Include only FB-highlighted additions in the main milestones table.
    source_b = m.auxiliary_tables["TASK"]
    source_u = m.auxiliary_update_tables["TASK"]
    extra_rows = []
    for activity_id, category in (("M.1100", "QC 2.2"), ("IST.1100", "IST / L4 Cx")):
        br = source_b[source_b["task_code"].eq(activity_id)]
        ur = source_u[source_u["task_code"].eq(activity_id)]
        if len(br) != 1 or len(ur) != 1:
            raise ValueError(f"Cannot uniquely reconcile DH1100 milestone {activity_id}")
        bd = pd.to_datetime(br.iloc[0]["target_end_date"], errors="coerce")
        cd = pd.to_datetime(ur.iloc[0]["reend_date"], errors="coerce")
        if pd.isna(bd) or pd.isna(cd):
            raise ValueError(f"Missing XER date for {activity_id}")
        extra_rows.append({
            "Area": "DH1100", "Milestone": category, "Activity ID": activity_id,
            "Baseline Finish": bd, "Current Finish": cd,
            "Variance (Working Days)": us_federal_workday_delay(bd, cd),
        })
    milestone_rows = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
    milestone_rows["Area"] = pd.Categorical(
        milestone_rows["Area"],
        categories=["DH1100", "DH1200", "DH1300", "DH1400", "DH1500", "DH1600"],
        ordered=True,
    )
    # Executive order: Data Hall ascending, QC 2.2 before IST / L4 Cx.
    milestone_rows["Milestone"] = pd.Categorical(
        milestone_rows["Milestone"],
        categories=["QC 2.2", "IST / L4 Cx"],
        ordered=True,
    )
    milestone_rows = milestone_rows.sort_values(
        ["Area", "Milestone"], kind="stable"
    ).reset_index(drop=True)

    display = milestone_rows[[
        "Area", "Milestone", "Activity ID", "Baseline Finish",
        "Current Finish", "Variance (Working Days)",
    ]].copy().rename(columns={
        "Area": "Data Hall",
        "Baseline Finish": "Baseline Date",
        "Current Finish": "Current Finish Date",
    })
    for date_field in ("Baseline Date", "Current Finish Date"):
        display[date_field] = display[date_field].apply(_fmt_date)

    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.dataframe(
            display, use_container_width=True, hide_index=True, height="content",
            column_config={
                "Variance (Working Days)": st.column_config.NumberColumn(
                    "Variance (Working Days)", format="%+d"
                ),
            },
        )
    with right:
        chart_rows = milestone_rows.dropna(subset=["Variance (Working Days)"])
        labels = [f"{r['Area']} · {r['Milestone']}" for _, r in chart_rows.iterrows()]
        values = chart_rows["Variance (Working Days)"].astype(int).tolist()
        fig = go.Figure(go.Bar(
            y=labels, x=values, orientation="h",
            marker_color=[RED if v > 0 else GREEN if v < 0 else BLUE for v in values],
            text=[f"{v:+d}" for v in values], textposition="outside",
            hovertemplate="%{y}<br>BL → U01 Finish shift: %{x:+d} working days<extra></extra>",
        ))
        lo, hi = min(0, *values), max(0, *values)
        margin = max(12, int(max(1, hi-lo) * .18))
        fig.update_layout(
            **_layout(560, 130, 88, 32),
            title="MILESTONE DATES DEVIATION · US WORKING DAYS",
            xaxis_title="Baseline vs Current Update · Working Days",
            showlegend=False,
        )
        fig.update_xaxes(range=[lo-margin if lo<0 else 0, hi+margin], zeroline=True,
                         zerolinecolor=GRID, gridcolor=GRID)
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_suffolk_l3_milestones(m: DC7Model):
    """Reproduce the user's Excel MILESTONES sheet using fixed baseline dates.

    The sheet is the immutable baseline reference. Forecast is sourced from
    Suffolk UP-08 only when an unambiguous P6 activity can be identified.
    Do not substitute old Excel forecasts or infer readiness/FTE rollups.
    """
    st.markdown(
        '<div class="section-caption">SUFFOLK · MILESTONES</div>',
        unsafe_allow_html=True,
    )
    task = m.update_tables["TASK"]
    task = task[task["proj_id"].astype(str).eq(str(m.update_project["proj_id"]))]
    template_rows = [
        ("FOH", "FOH-010", "Priority Rooms - Ready to Receive Equipment", "2026-08-03", None),
        ("FOH", "FOH-020", "Early Access", "2026-12-03", "FOH.MS-2"),
        ("FOH", "FOH-030", "Commissioning & Start Up // L3 Start-Up", "2026-08-10", "HSE-SYS-STU-1"),
        ("FOH", "FOH-040", "Substantial Completion - TCO", "2026-12-31", "FOH.MS-4"),
        ("BOH", "BOH-010", "Priority Rooms - Ready to Receive Equipment", "2026-09-25", None),
        ("BOH", "BOH-020", "Early Access", "2026-11-24", "BOH-MS-2"),
        ("BOH", "BOH-030", "Commissioning & Start Up // L3 Start-Up", "2026-11-03", "HSE-SYS-STU-4"),
        ("BOH", "BOH-040", "Substantial Completion - TCO", "2026-12-31", "BOH-MS-4"),
        ("DH1100", "DH1100-010", "Electrical Room - Ready to Receive Equipment", "2026-08-10", None),
        ("DH1100", "DH1100-020", "OFCI - First Skid Shipment Delivery", "2026-08-31", None),
        ("DH1100", "DH1100-030", "Electrical Equipment - FTE Ready", "2026-10-08", None),
        ("DH1100", "DH1100-040", "L3 Commissioning - Start", "2026-11-04", "DH1100.L3CX.000"),
        ("DH1100", "DH1100-050", "Milestone 1 - Early Access", "2026-12-03", "M1150"),
        ("DH1100", "DH1100-060", "Milestone 7 - Substantial Completion - TCO", "2026-12-31", "DH1100.4020"),
        ("DH1200", "DH1200-010", "Electrical Room - Ready to Receive Equipment", "2026-08-12", None),
        ("DH1200", "DH1200-020", "OFCI - First Skid Shipment Delivery", "2026-10-06", None),
        ("DH1200", "DH1200-030", "Electrical Equipment - FTE Ready", "2026-10-26", None),
        ("DH1200", "DH1200-040", "L3 Commissioning - Start", "2026-10-27", "DH1200.L3CX.39"),
        ("DH1200", "DH1200-050", "Milestone 1 - Early Access", "2026-12-31", "DH1200.4010"),
        ("DH1200", "DH1200-060", "Milestone 7 - Substantial Completion - TCO", "2027-02-01", "DH1200.4020"),
        ("DH1300", "DH1300-010", "Electrical Room - Ready to Receive Equipment", "2026-08-11", None),
        ("DH1300", "DH1300-020", "OFCI - First Skid Shipment Delivery", "2026-11-07", None),
        ("DH1300", "DH1300-030", "Electrical Equipment - FTE Ready", "2026-12-30", None),
        ("DH1300", "DH1300-040", "L3 Commissioning - Start", "2026-10-28", "DH1300.L3CX.59"),
        ("DH1300", "DH1300-050", "Milestone 1 - Early Access", "2027-02-01", "DH1300.4010"),
        ("DH1300", "DH1300-060", "Milestone 7 - Substantial Completion - TCO", "2027-03-01", "DH1300.4020"),
        ("DH1400", "DH1400-010", "Electrical Room - Ready to Receive Equipment", "2026-09-16", None),
        ("DH1400", "DH1400-020", "OFCI - First Skid Shipment Delivery", "2026-12-08", None),
        ("DH1400", "DH1400-030", "Electrical Equipment - FTE Ready", "2027-02-01", None),
        ("DH1400", "DH1400-040", "L3 Commissioning - Start", "2027-01-29", "DH1400.L3CX.79"),
        ("DH1400", "DH1400-050", "Milestone 1 - Early Access", "2027-03-01", "DH2100.4010"),
        ("DH1400", "DH1400-060", "Milestone 7 - Substantial Completion - TCO", "2027-04-01", "DH2100.4020"),
        ("DH1500", "DH1500-010", "Electrical Room - Ready to Receive Equipment", "2026-08-24", None),
        ("DH1500", "DH1500-020", "OFCI - First Skid Shipment Delivery", "2027-01-09", None),
        ("DH1500", "DH1500-030", "Electrical Equipment - FTE Ready", "2027-03-04", None),
        ("DH1500", "DH1500-040", "L3 Commissioning - Start", "2026-11-23", "DH1500.L3CX.99"),
        ("DH1500", "DH1500-050", "Milestone 1 - Early Access", "2027-04-01", "DH2200.4010"),
        ("DH1500", "DH1500-060", "Milestone 7 - Substantial Completion - TCO", "2027-04-30", "DH2200.4020"),
        ("DH1600", "DH1600-010", "Electrical Room - Ready to Receive Equipment", "2026-08-17", None),
        ("DH1600", "DH1600-020", "OFCI - First Skid Shipment Delivery", "2027-02-06", None),
        ("DH1600", "DH1600-030", "Electrical Equipment - FTE Ready", "2027-03-19", None),
        ("DH1600", "DH1600-040", "L3 Commissioning - Start", "2027-03-22", "DH1600.L3CX.19"),
        ("DH1600", "DH1600-050", "Milestone 1 - Early Access", "2027-04-30", "DH2300.4010"),
        ("DH1600", "DH1600-060", "Milestone 7 - Substantial Completion - TCO", "2027-06-01", "DH2300.4020"),
    ]
    results = []
    previous_area = None
    for area, reference, name, baseline_iso, code in template_rows:
        if area != previous_area:
            results.append({
                "Reference": "", "Milestones": area,
                "Baseline": "", "Forecast": "", "Variance": "",
            })
            previous_area = area
        baseline = pd.Timestamp(baseline_iso)
        current = pd.NaT
        if code is not None:
            matched = task[task["task_code"].astype(str).eq(code)]
            if len(matched) == 1:
                activity = matched.iloc[0]
                status = str(activity.get("status_code", ""))
                date_field = "act_end_date" if status == "TK_Complete" else "reend_date"
                current = pd.to_datetime(activity.get(date_field), errors="coerce")
                if pd.isna(current) and status != "TK_Complete":
                    current = pd.to_datetime(activity.get("target_end_date"), errors="coerce")
        # This is a calendar-day difference, not a P6 calendar calculation.
        shift = (baseline.normalize() - current.normalize()).days if pd.notna(current) else None
        results.append({
            "Reference": reference,
            "Milestones": name,
            "Baseline": _fmt_date(baseline),
            "Forecast": _fmt_date(current) if pd.notna(current) else "—",
            "Variance": f"{shift:+d}" if shift is not None else "—",
        })
    # Keep the Excel grouping and row order, including readiness and delivery.
    df = pd.DataFrame(results)
    st.dataframe(
        df, use_container_width=True, hide_index=True, height="content",
    )


def render_dashboard(helix: DC7Model, suffolk: DC7Model):
    view = st.session_state.get("dc7_schedule_view", "SUFFOLK")
    if view not in ("SUFFOLK", "HELIX"):
        view = "SUFFOLK"
    model = suffolk if view == "SUFFOLK" else helix
    st.markdown(CSS, unsafe_allow_html=True)
    render_header(model, view)
    # Keep the native control in its own Streamlit layout row, separated from the HTML header.
    with st.container(border=True):
        left_nav, center_nav, right_nav = st.columns([3, 2, 3], gap="small")
        with center_nav:
            st.segmented_control(
                "Schedule View", ["SUFFOLK", "HELIX"],
                default="SUFFOLK", key="dc7_schedule_view",
                label_visibility="collapsed",
            )
    schedule_title = (
        "SUFFOLK SCHEDULE – HELIX SCOPE ONLY"
        if view == "SUFFOLK" else "HELIX SCHEDULE – ELECTRICAL LINE-UPS"
    )
    st.markdown(
        f'<div class="project-strip"><span>{_safe(schedule_title)}</span></div>',
        unsafe_allow_html=True,
    )
    if view == "HELIX":
        # No shared SUFFOLK construction KPI/curve data in HELIX VIEW.
        # All HELIX summary/curve/status/line-up widgets use official
        # 226021-HE.B independent electrical Baseline only.
        render_helix_kpis(helix)
        render_helix_baseline_scurve_and_status(helix)
        render_helix_lineup_stats(helix)
        # Do not call render_progress_detail(helix, view="HELIX"):
        # its QTS-DASH group breakdown duplicates the SUFFOLK view.
        render_helix_lineups(helix)
        # New independent HELIX contractual-date comparison. Do not restore
        # the former SUFFOLK/FTE-Ready logic or label baseline as Current.
        render_helix_contract_milestones(helix)
        return

    render_kpis(suffolk, "SUFFOLK")
    render_scurve_and_status(suffolk)
    render_stats(suffolk, "PROJECT PROGRESS BY AREA")
    render_windows(suffolk)
    render_progress_detail(suffolk, view="SUFFOLK")
    render_suffolk_l3_milestones(suffolk)

    # Maintain the detailed SUFFOLK Construction activity/WBS audit reports
    # in the validated model; do not display separate audit/download panels
    # in the executive dashboard (FB review p4). No records are discarded.
