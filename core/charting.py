# -*- coding: utf-8 -*-
"""
Builds the candlestick + RSI chart (Plotly) for one symbol/timeframe,
overlaying SMC zones (Order Blocks, FVGs) and the pivot-to-pivot divergence
lines, plus an optional Entry / SL / Target trade-plan overlay.
"""

from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {
    "bg": "#0a0e14", "panel": "#10161f", "grid": "#1f2937", "text": "#e6edf3",
    "bull": "#17c384", "bear": "#ff5470", "accent": "#00e5a0", "accent2": "#3ea6ff",
    "gold": "#f0b90b", "ob_bull": "rgba(23,195,132,0.14)", "ob_bear": "rgba(255,84,112,0.14)",
    "fvg_bull": "rgba(0,229,160,0.08)", "fvg_bear": "rgba(255,84,112,0.08)",
}

STATUS_COLOR = {"Active": "#00e5a0", "Pending": "#f0b90b", "False": "#8b98a5"}


def build_chart(
    df: pd.DataFrame,
    rsi: pd.Series,
    fvgs: List,
    obs: List,
    signals_with_status: List[tuple],
    trade_plan=None,
    max_bars: int = 200,
    title: str = "",
):
    """signals_with_status: list of (DivergenceSignal, status) — pivot lines are
    drawn for all of them (color-coded by status); trade_plan (if given) is drawn
    as Entry/SL/Target horizontal lines, labelled against trade_plan_signal."""
    plot_df = df.tail(max_bars)
    start_pos = len(df) - len(plot_df)  # offset to translate absolute bar-pos -> plot_df index

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=plot_df.index, open=plot_df["Open"], high=plot_df["High"],
            low=plot_df["Low"], close=plot_df["Close"],
            increasing_line_color=COLORS["bull"], decreasing_line_color=COLORS["bear"],
            increasing_fillcolor=COLORS["bull"], decreasing_fillcolor=COLORS["bear"],
            name="Price",
        ),
        row=1, col=1,
    )

    # --- Order Block zones ---
    for ob in obs:
        if ob.pos < start_pos or ob.mitigated:
            continue
        x0 = plot_df.index[ob.pos - start_pos]
        x1 = plot_df.index[-1]
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=ob.bottom, y1=ob.top,
            fillcolor=COLORS["ob_bull"] if ob.kind == "bullish" else COLORS["ob_bear"],
            line=dict(width=0), row=1, col=1, layer="below",
        )

    # --- FVG zones (last few only, to avoid clutter) ---
    recent_fvgs = [f for f in fvgs if f.pos >= start_pos][-15:]
    for f in recent_fvgs:
        x0 = plot_df.index[f.pos - start_pos]
        x1 = plot_df.index[min(f.pos - start_pos + 12, len(plot_df) - 1)]
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=f.bottom, y1=f.top,
            fillcolor=COLORS["fvg_bull"] if f.kind == "bullish" else COLORS["fvg_bear"],
            line=dict(width=0.5, color=COLORS["grid"]), row=1, col=1, layer="below",
        )

    # --- RSI panel ---
    fig.add_trace(
        go.Scatter(x=plot_df.index, y=rsi.tail(max_bars), line=dict(color=COLORS["accent2"], width=1.6),
                    name="RSI"),
        row=2, col=1,
    )
    fig.add_hline(y=70, line=dict(color=COLORS["bear"], width=1, dash="dot"), row=2, col=1)
    fig.add_hline(y=30, line=dict(color=COLORS["bull"], width=1, dash="dot"), row=2, col=1)
    fig.add_hline(y=50, line=dict(color=COLORS["grid"], width=1), row=2, col=1)

    # --- Divergence pivot-to-pivot lines (price + RSI), color-coded by status ---
    for sig, status in signals_with_status:
        if sig.p1.pos < start_pos:
            continue
        color = STATUS_COLOR.get(status, "#8b98a5")
        x1_, x2_ = plot_df.index[sig.p1.pos - start_pos], plot_df.index[sig.p2.pos - start_pos]
        fig.add_trace(go.Scatter(
            x=[x1_, x2_], y=[sig.p1.price, sig.p2.price], mode="lines+markers",
            line=dict(color=color, width=2, dash="solid" if status == "Active" else "dot"),
            marker=dict(size=6, color=color),
            name=f"{sig.div_type} ({status})", showlegend=True,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[x1_, x2_], y=[sig.p1.rsi, sig.p2.rsi], mode="lines+markers",
            line=dict(color=color, width=2, dash="solid" if status == "Active" else "dot"),
            marker=dict(size=6, color=color), showlegend=False,
        ), row=2, col=1)

    # --- Trade plan overlay ---
    if trade_plan is not None:
        tp = trade_plan
        for y, label, color in [
            (tp.entry, f"Entry {tp.entry:.2f}", COLORS["accent2"]),
            (tp.stop_loss, f"SL {tp.stop_loss:.2f}", COLORS["bear"]),
            (tp.target1, f"T1 {tp.target1:.2f} ({tp.rr1:.1f}R)", COLORS["gold"]),
            (tp.target2, f"T2 {tp.target2:.2f} ({tp.rr2:.1f}R)", COLORS["bull"]),
        ]:
            fig.add_hline(
                y=y, line=dict(color=color, width=1.3, dash="dash"),
                annotation_text=label, annotation_position="right",
                annotation_font=dict(color=color, size=11), row=1, col=1,
            )

    fig.update_layout(
        height=560, template="plotly_dark",
        paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"]), title=title,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1, gridcolor=COLORS["grid"])
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100], gridcolor=COLORS["grid"])
    fig.update_xaxes(gridcolor=COLORS["grid"])
    return fig
