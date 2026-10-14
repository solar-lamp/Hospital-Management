"""Plotly chart helpers with a consistent, colour-blind-checked palette.

Categorical colours are assigned in a fixed order and follow the entity
(e.g. an appointment status keeps its colour whatever the filter)."""

import plotly.graph_objects as go

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6",
           "#e34948"]

STATUS_COLORS = {
    "SCHEDULED": PALETTE[0], "CONFIRMED": PALETTE[6], "COMPLETED": PALETTE[2],
    "CANCELLED": PALETTE[1], "NO_SHOW": PALETTE[4],
}


def style(fig: go.Figure, height: int = 320, y_title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    title=None),
        hovermode="x unified", bargap=0.25,
        font=dict(family="sans-serif", size=13),
    )
    fig.update_xaxes(showgrid=False, title=None, linecolor="rgba(128,128,128,0.4)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False, title=y_title,
                     rangemode="tozero")
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    return fig
