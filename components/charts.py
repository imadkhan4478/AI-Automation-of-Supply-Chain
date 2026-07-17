"""
Chart helpers — all charts are Plotly, themed consistently via theme.py.

Pages call these instead of building Plotly figures inline, so every chart
in the app shares the same fonts, colors, and styling.
"""

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from components import theme as T


def _apply_layout(fig, height=300, legend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=T.FONT_STACK, color=T.INK, size=13),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor=T.NAVY, font_size=12, font_family=T.FONT_STACK),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=T.LINE, tickfont=dict(color=T.MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=T.CANVAS_ALT, zeroline=False, tickfont=dict(color=T.MUTED))
    return fig


def trend_line(df, x, y, height=300):
    """Smooth trend line with a soft fill — for values over time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="lines+markers",
        line=dict(color=T.NAVY, width=3, shape="spline"),
        marker=dict(size=7, color=T.GOLD, line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(31,45,78,0.06)",
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def ranked_bar(df, cat, val, height=320, benchmark=None, invert_color=False):
    """Horizontal ranked bar — for supplier performance, top items, etc."""
    d = df.sort_values(val, ascending=True)
    colors = [T.NAVY] * len(d)
    if invert_color:  # worst (highest) gets risk color
        mx = d[val].max()
        colors = [T.RISK if v == mx else T.NAVY for v in d[val]]
    fig = go.Figure(go.Bar(
        x=d[val], y=d[cat], orientation="h",
        marker=dict(color=colors),
        hovertemplate="%{y}<br><b>%{x}</b><extra></extra>",
    ))
    if benchmark is not None:
        fig.add_vline(x=benchmark, line_dash="dash", line_color=T.GOLD,
                      annotation_text="target", annotation_font_color=T.GOLD)
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def category_bar(df, cat, val, height=300):
    """Vertical bar for category comparison."""
    fig = go.Figure(go.Bar(
        x=df[cat], y=df[val],
        marker=dict(color=T.NAVY),
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def donut(labels, values, height=300):
    """Donut for composition (status split, stock health)."""
    # map status-like labels to semantic colors where possible
    colors = []
    for lbl in labels:
        fg, _ = T.status_colors(lbl)
        colors.append(fg if fg != T.INFO else T.NAVY)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="label+percent", textfont=dict(size=12),
        hovertemplate="%{label}<br><b>%{value}</b> (%{percent})<extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height, legend=False), width="stretch", config={"displayModeBar": False})


def aging_buckets(df, bucket_col, count_col, height=300):
    """Aging analysis — buckets colored by severity (green->red)."""
    order = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]
    sev = {"0-30 days": T.HEALTHY, "31-60 days": T.WATCH,
           "61-90 days": "#D98800", "90+ days": T.RISK}
    d = df.set_index(bucket_col).reindex(order).reset_index()
    fig = go.Figure(go.Bar(
        x=d[bucket_col], y=d[count_col],
        marker=dict(color=[sev.get(b, T.NAVY) for b in d[bucket_col]]),
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})
