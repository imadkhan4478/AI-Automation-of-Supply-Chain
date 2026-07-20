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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=T.MUTED)),
        # bgcolor here is a fixed brand color (not mode-dependent, see theme.py),
        # so the hover font color is pinned to white rather than left to
        # Plotly's default -- which doesn't auto-contrast against a dark chip.
        hoverlabel=dict(bgcolor=T.BRAND_DEEP, font=dict(color="white", size=12, family=T.FONT_STACK)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=T.LINE, tickfont=dict(color=T.MUTED))
    # Gridlines use T.LINE (the border/divider token, already tuned for
    # visibility against T.CANVAS in both modes) rather than T.CANVAS_ALT,
    # which in dark mode sits too close in luminance to the canvas to read.
    fig.update_yaxes(showgrid=True, gridcolor=T.LINE, zeroline=False, tickfont=dict(color=T.MUTED))
    return fig


def trend_line(df, x, y, height=300):
    """Smooth trend line with a brand-gradient fill — for values over time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="lines+markers",
        line=dict(color=T.BRAND, width=3, shape="spline"),
        marker=dict(size=7, color=T.VIOLET, line=dict(color=T.CANVAS, width=1.5)),
        fill="tozeroy",
        fillgradient=dict(
            type="vertical",
            colorscale=[[0, "rgba(79,70,229,0.02)"], [1, "rgba(79,70,229,0.28)"]],
        ),
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def ranked_bar(df, cat, val, height=320, benchmark=None, invert_color=False):
    """Horizontal ranked bar — for supplier performance, top items, etc.

    Default bars use a sequential brand-gradient (light -> deep indigo) keyed
    to the bar's own value, so magnitude reads at a glance even without the
    risk highlight. `invert_color` overrides this: the worst (highest) bar
    turns risk-red and the rest fall back to a flat brand tone, since that
    mode is about flagging one outlier, not showing a gradient of magnitude.
    """
    d = df.sort_values(val, ascending=True)
    if invert_color:  # worst (highest) gets risk color
        mx = d[val].max()
        marker = dict(color=[T.RISK if v == mx else T.BRAND for v in d[val]])
    else:
        marker = dict(color=d[val], colorscale=[[0, T.BRAND_LIGHT], [1, T.BRAND_DEEP]])
    fig = go.Figure(go.Bar(
        x=d[val], y=d[cat], orientation="h",
        marker=marker,
        hovertemplate="%{y}<br><b>%{x}</b><extra></extra>",
    ))
    if benchmark is not None:
        fig.add_vline(x=benchmark, line_dash="dash", line_color=T.GOLD,
                      annotation_text="target", annotation_font_color=T.GOLD)
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def category_bar(df, cat, val, height=300):
    """Vertical bar for category comparison, brand-gradient by magnitude."""
    fig = go.Figure(go.Bar(
        x=df[cat], y=df[val],
        marker=dict(color=df[val], colorscale=[[0, T.BRAND_LIGHT], [1, T.BRAND_DEEP]]),
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})


def donut(labels, values, height=300):
    """Donut for composition (status split, stock health).

    Labels sit outside the ring (not curved along thin slice arcs) -- with
    more than a handful of categories, Plotly's default "inside" placement
    rotates each label to follow its own slice, and on thin slices that
    means overlapping/truncated text (e.g. "Ready Awaiting Sailing" reading
    as "aiting Sailing" crossed with the next slice's label). `automargin`
    lets Plotly grow the figure's own margins to fit the outside labels
    instead of clipping them.
    """
    # map status-like labels to semantic colors where possible
    colors = []
    for lbl in labels:
        fg, _ = T.status_colors(lbl)
        colors.append(fg if fg != T.INFO else T.BRAND)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color=T.CANVAS, width=2)),
        textinfo="label+percent", textposition="outside", automargin=True,
        textfont=dict(size=11),
        hovertemplate="%{label}<br><b>%{value}</b> (%{percent})<extra></extra>",
    ))
    fig = _apply_layout(fig, height, legend=False)
    fig.update_layout(margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def aging_buckets(df, bucket_col, count_col, height=300):
    """Aging analysis — buckets colored by severity (green->red)."""
    order = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]
    sev = {"0-30 days": T.HEALTHY, "31-60 days": T.WATCH,
           "61-90 days": "#D98800", "90+ days": T.RISK}
    d = df.set_index(bucket_col).reindex(order).reset_index()
    fig = go.Figure(go.Bar(
        x=d[bucket_col], y=d[count_col],
        marker=dict(color=[sev.get(b, T.BRAND) for b in d[bucket_col]]),
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>",
    ))
    st.plotly_chart(_apply_layout(fig, height), width="stretch", config={"displayModeBar": False})
